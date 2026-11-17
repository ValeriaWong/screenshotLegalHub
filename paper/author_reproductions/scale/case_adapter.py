"""论文出处：Khatri et al., SCALE, EMNLP 2026.
https://aclanthology.org/2026.emnlp-main.36/
作者代码：https://github.com/khatrimann/SCALE @ 1700924ca8c448af56c854e5e4c9ae693e86beb3.
复现程度：作者原阶段/检索函数＋明确的产品任务适配；不是原论文benchmark复现。
原方法/创新：独立指南构建Issue–Factor层级，按案件选择问题与因素，沿¶映射
检索指南段落，再迭代更新法律分析。原输入是ECHR案例、公约条文、Case-law Guides；
原输出是问题/因素/段落路径及LAW分析；原benchmark为ECHR法律推理专家评估。
原任务入口：同目录product_adapter.py，已运行公开案例001-231088的两个条文。
本文件输入：冻结法源legal_corpus、可选独立factor_hierarchy、来源标识/引用单元和
案件陈述；输出：CaseAnalysisOutput及独立的hierarchy/selected paragraphs/updates。
适配：不加载任何本地模型权重。作者StageProcessing(3/4)、ReasoningStage、
filter_issues/extract_paras/extract_selected_paragraphs/batch_paras函数体保持不变；
Stage I/II调用作者公开prompt（原仓库阶段类仅实现3/4/5），组装调度在此文件。
法律域由ECHR指南改为冻结中国法源，完整记录原/新prompt及hash；不引入ECHR法源。
Stage I/II绝不接收案件事实/问题/Gold。派生层级未经专家审查，不提升源文本等级。
本项目保留陈述、否认和未知；不声称法院已认定事实。最终JSON投影为产品新增步骤。
限制：法规集合替代判例指南，不能检验论文的先例覆盖收益；没有法律准确率结论。
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from author_runtime import source, call, tool, emit, original_definitions


def execute(request):
    folder, provenance = source('scale')
    import tiktoken
    from fuzzywuzzy import fuzz
    tokenizer = tiktoken.get_encoding('cl100k_base')
    legal = request['legal_corpus']
    if not legal or any(not s.get('text') for s in legal):
        raise ValueError('SCALE需要独立冻结法源原文；不能由案件或Gold补造')
    if len({s['id'] for s in legal}) != len(legal):
        raise ValueError('法源ID重复')
    paragraphs = {i: dict(source_id=s['id'], text=s['text'], metadata=s)
                  for i, s in enumerate(legal, 1)}
    # The author's regex reads the serialized, numbered JSON strings, just as in its guides.
    serialized = json.dumps([str(i)+'. '+s['text'] for i,s in paragraphs.items()], ensure_ascii=False, indent=2)
    def guide_open(path, *args, **kwargs):
        if str(path).replace(chr(92),'/') != 'Guides/JSON/GUIDE_ART_FROZEN_LAW_ENG.json':
            raise ValueError('Only the frozen product guide may be read')
        return io.StringIO(serialized)
    helpers = original_definitions(folder/'utils.py',
        ['filter_issues','extract_paras','extract_selected_paragraphs','batch_paras'],
        dict(re=re,os=os,tokenizer=tokenizer,fuzz=fuzz,open=guide_open))
    spec = importlib.util.spec_from_file_location('scale_original_prompts',folder/'prompts.py')
    original_prompts = importlib.util.module_from_spec(spec);spec.loader.exec_module(original_prompts)
    adapted = types.ModuleType('prompts'); changes = {}
    domain = ('\n任务域适配：仅依据本次冻结法源，中文输出。材料是待核实陈述，不是法院认定。'
              '不得加入欧洲人权公约规则、外部先例或未提供法条。保留否认与未知。'
              '层级行首必须是Issue 数字:，因素使用Factor 字母:；每个因素必须有独立¶数字引用。')
    for name in ['STAGE1_SYSTEM_PROMPT','STAGE2_SYSTEM_PROMPT','STAGE3_ITER_SYSTEM_PROMPT','STAGE4_SYSTEM_PROMPT']:
        old = getattr(original_prompts,name)
        new = old.replace('European Court of Human Rights (ECHR) jurisprudence','the supplied frozen legal sources')
        new = new.replace('European Court of Human Rights (ECHR)', 'supplied legal sources')
        new = new.replace('ECHR Case Facts','unverified source statements').replace('case law guide','frozen legal source').replace('Convention','supplied law')
        new += domain
        setattr(adapted,name,new)
        changes[name] = dict(original=old,adapted=new,original_sha256=hashlib.sha256(old.encode()).hexdigest(),adapted_sha256=hashlib.sha256(new.encode()).hexdigest())
    old = original_prompts.STAGE_REASONING_ITER_SYSTEM_PROMPT
    new = ('你是证据研究助手。沿用逐批更新结构，依据CASE LAW GUIDE PARAGRAPHS中的冻结法源'
           '更新PREVIOUS_LAW分析。输出中文公开分析：当事人陈述、法源适用、证据支持与缺口、条件性结论。'
           '¶编号仅指提供的独立法源段落；原文陈述未获司法确认。不得虚构案例、公约规则或判决。'
           '引用仅来自本次材料；没有证据或规则则明确未知。先前分析是模型草稿，随新材料纠正。')
    adapted.STAGE_REASONING_ITER_SYSTEM_PROMPT=new
    changes['STAGE_REASONING_ITER_SYSTEM_PROMPT']=dict(original=old,adapted=new,original_sha256=hashlib.sha256(old.encode()).hexdigest(),adapted_sha256=hashlib.sha256(new.encode()).hexdigest())
    sys.modules['prompts']=adapted
    stub=types.ModuleType('LLMClient');stub.LLMClient=None;sys.modules['LLMClient']=stub
    sys.path.insert(0,str(folder))
    import stage_processing as original
    original.prompts=adapted
    phase='';counter=0
    class Transport:
        provider='stdio'
        def create(self,messages,**parameters):
            nonlocal counter
            stage=phase+'.'+str(counter);counter+=1
            return call(stage,messages,dict(model='author-model-replaced-by-parent',**parameters))
    client=Transport();original.StageProcessing.client=client
    tool('scale.product_prompt_adaptations',changes)
    hierarchy=request.get('factor_hierarchy')
    hierarchy_origin='provided_independent_hierarchy' if hierarchy else 'model_derived_from_frozen_law_only'
    if hierarchy:
        ids={p['source_id']:i for i,p in paragraphs.items()}
        blocks=[]
        for n,issue in enumerate(hierarchy,1):
            lines=['Issue '+str(n)+': '+issue['label']]
            for f in issue['factors']:
                refs=f['guide_source_ids']
                if not refs or not set(refs)<=set(ids):raise ValueError('层级引用不属于冻结法源')
                lines.append('  Factor '+f['id']+': '+f['label']+' ('+', '.join('¶'+str(ids[s]) for s in refs)+')')
            blocks.append('\n'.join(lines))
        hierarchy='\n\n'.join(blocks)
    else:
        # Independent legal material only: case input and its question are deliberately absent.
        guides=['¶'+str(i)+' '+json.dumps(p['metadata'],ensure_ascii=False) for i,p in paragraphs.items()]
        independent=[]
        for batch in helpers['batch_paras'](guides,thresh=1000):
            if not batch:continue
            phase='guide_extract'
            independent.append(client.create([dict(role='system',content=adapted.STAGE1_SYSTEM_PROMPT),dict(role='user',content='\n\n'.join(batch))],temperature=0.))
        phase='guide_merge'
        hierarchy=client.create([dict(role='system',content=adapted.STAGE2_SYSTEM_PROMPT),dict(role='user',content='\n\n'.join(independent))],temperature=0.)
    parts=re.split(r'(?m)^(Issue \d+:[^\n]*)',hierarchy)
    blocks={parts[i].strip():parts[i]+parts[i+1] for i in range(1,len(parts)-1,2)}
    if not blocks:raise ValueError('法源派生层级缺少Issue标题；保留原回复，不自动补造')
    for block in blocks.values():
        ids=helpers['extract_paras'](block)
        if not ids or not set(ids)<=set(paragraphs):raise ValueError('派生层级缺少有效¶引用')
    tool('scale.product_independent_guide',dict(hierarchy=hierarchy,origin=hierarchy_origin,review_status='not_expert_reviewed',paragraphs=paragraphs))
    facts=json.dumps(dict(goal=request['question'],sources=request['sources']),ensure_ascii=False)
    phase='issues'
    selected,history,responses=original.StageProcessing(3,facts,issues=list(blocks),stage3_thresh=1000).process()
    matched=helpers['filter_issues'](list(blocks),[s.strip() for s in selected.splitlines() if s.strip()]) if selected.strip()!='NO' else []
    selected_blocks='\n'.join(blocks[k] for k in dict.fromkeys(k for k,score in matched) if k)
    chosen='NO';paragraph_ids=[];guide_paragraphs=[];updates=[]
    if selected_blocks:
        phase='factors'
        chosen=original.StageProcessing(4,facts,issues=selected,factors=selected_blocks).process()
        paragraph_ids=helpers['extract_paras'](chosen)
        allowed=set(helpers['extract_paras'](selected_blocks))
        if not set(paragraph_ids)<=allowed:raise ValueError('因素选择引用超出所选问题的冻结法源')
        if chosen.strip()!='NO' and not paragraph_ids:raise ValueError('因素回复未给出¶引用')
        guide_paragraphs=helpers['extract_selected_paragraphs']('FROZEN_LAW',paragraph_ids)
        previous='NONE: ITERATION 1: DO NOT CONSIDER THIS'
        for batch in helpers['batch_paras'](guide_paragraphs):
            if not batch:continue
            phase='reasoning'
            stage=original.ReasoningStage(facts,'\n\n'.join(batch),'FROZEN_LAW')
            previous=client.create(stage.get_stage_prompt(previous),temperature=0.)
            updates.append(previous)
    path=dict(issues=selected,issue_matches=matched,factors=chosen,guide_paragraph_ids=paragraph_ids,guide_paragraphs=guide_paragraphs,updates=updates)
    tool('scale.product_issue_factor_guide_path',path)
    phase='project_output'
    raw=client.create([dict(role='system',content=request['instruction']+' 将已执行的SCALE分析投影为指定JSON；原文定位只用sources的citation_units。¶段落号是法律材料编号，不是案件证据位置；没有适用因素时保留不确定性，不补造规则。'),dict(role='user',content=json.dumps(dict(goal=request['question'],sources=request['sources'],legal_corpus=legal,scale_analysis=path),ensure_ascii=False))],temperature=0.)
    output=json.loads(raw)
    return dict(event='result',method='scale',output=output,paths=path,hierarchy=hierarchy,hierarchy_origin=hierarchy_origin,
        hierarchy_review_status='not_expert_reviewed',paragraphs=paragraphs,prompt_adaptations=changes,calls=counter,
        source_commit=provenance['commit'],author_entry='Stage I/II original prompts -> StageProcessing(3,4) -> extract_paras -> extract_selected_paragraphs -> batch_paras -> ReasoningStage',
        original_model_weights_used=False,local_model_inference=False,original_complete_benchmark=False,
        task_adaptations=['Chinese frozen laws replace ECHR case-law guides','Stage I/II source-only dispatch','Chinese research reasoning prompt replaces court judgment prompt','CaseAnalysisOutput projection'],
        product_adaptation_completed=True,expert_legal_accuracy=None)

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=execute(request)
    emit(result)
