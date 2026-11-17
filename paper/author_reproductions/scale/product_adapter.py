"""论文出处：Khatri et al., SCALE, EMNLP 2026.
https://aclanthology.org/2026.emnlp-main.36/
作者源码：https://github.com/khatrimann/SCALE @ 1700924ca8c448af56c854e5e4c9ae693e86beb3.
复现程度：原 StageProcessing(3/4)、ReasoningStage、filter_issues、extract_paras、
extract_selected_paragraphs 和 batch_paras 原样加载；使用作者已发布的 Issue–Factor
层级（Stage I/II 离线构建产物），不以新 prompt 模仿上述算法。该文件组合原公开组件；
仓库未提供可直接运行的 Stage 3/4 批量总调度脚本，因此输入/批次/资源装配由此适配器承担。
原方法：指南→Issue–Factor 层级→案例问题/因素匹配→¶指南段落→迭代法律分析。
创新：根据潜在法律问题/因素导航，保留指南段落关联；区别于仅按表面文本相似度检索。
原输入示例：ECHR Case facts + Articles [1_PROTOCOL_1,6_CIVIL] + 作者指南与层级。
原输出示例：选中issues/factors/¶编号、对应Case-law Guide段落、逐批更新的条文分析。
原benchmark：作者ECHR案例/文章级法律推理设置，专家评估问题识别与判例使用等维度；
不是KIE/DocVQA。此处仅原任务开发样例，未运行完整评测，也未执行原模型权重。
适配调试：LLMClient仅替换为父进程AIPING传输；原Qwen/Llama底座替换DeepSeek并记录；
文件路径相对锁定仓库，UTF-8解码；原模块os.nice/全部云SDK导入不执行；算法函数体不变。
对本项目：适合有明确法域、经审查指南和Issue–Factor→¶映射的法律全局问答。
不能直接做像素KIE，也不能将ECHR指南当中国法律；中国截图产品适配尚未接入，
缺少可引用的中国指南/映射是方法资源缺口，不是专家评测金标缺口。
"""
import contextlib,json,os,re,sys,types,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import ROOT,source,call,tool,emit,original_definitions

def execute(request):
    if request.get('mode')!='native':raise ValueError('SCALE中国截图适配未完成；不能自动使用ECHR指南回答中国法律问题')
    folder,provenance=source('scale');sys.path.insert(0,str(folder));os.chdir(folder)
    import tiktoken
    from fuzzywuzzy import fuzz
    # Do not import the multi-provider client: its transport is replaced, algorithms are not.
    stub=types.ModuleType('LLMClient');stub.LLMClient=None;sys.modules['LLMClient']=stub
    import stage_processing as original
    tokenizer=tiktoken.get_encoding('cl100k_base')
    def utf8_open(path,mode='r',*args,**kwargs):
        if 'b' not in mode:kwargs.setdefault('encoding','utf-8')
        return open(path,mode,*args,**kwargs)
    helpers=original_definitions(folder/'utils.py',['filter_issues','extract_paras','extract_selected_paragraphs','batch_paras'],dict(re=re,os=os,tokenizer=tokenizer,fuzz=fuzz,open=utf8_open))
    phase='';counter=0
    class Transport:
        provider='stdio'
        def create(self,messages,**params):
            nonlocal counter
            stage=phase+'.'+str(counter);counter+=1
            return call(stage,messages,dict(model='Qwen/Qwen3-8B',**params))
    client=Transport();original.StageProcessing.client=client
    outputs={};traces={}
    for article in request['articles']:
        hierarchy=(folder/'Hierarchies/Iter'/('article_'+article+'.txt')).read_text(encoding='utf-8')
        pieces=re.split(r'(?m)^(Issue \d+:[^\n]*)',hierarchy)
        blocks={pieces[i].strip():pieces[i]+pieces[i+1] for i in range(1,len(pieces)-1,2)}
        issues=list(blocks)
        if not issues:raise ValueError('Original issue hierarchy missing: '+article)
        phase='issues.'+article
        selected,prompt_history,response_history=original.StageProcessing(3,request['facts'],issues=issues,stage3_thresh=1000).process()
        predicted=[line.strip() for line in selected.splitlines() if line.strip()]
        matched=helpers['filter_issues'](issues,predicted)
        selected_blocks='\n'.join(blocks[k] for k in dict.fromkeys(k for k,_ in matched) if k)
        if not selected_blocks:raise ValueError('No issue matched original hierarchy')
        phase='factors.'+article
        selected_factors=original.StageProcessing(4,request['facts'],issues=selected,factors=selected_blocks).process()
        paragraph_ids=helpers['extract_paras'](selected_factors)
        if not paragraph_ids:raise ValueError('No original ¶ references returned for '+article)
        paragraphs=helpers['extract_selected_paragraphs'](article,paragraph_ids)
        batches=helpers['batch_paras'](paragraphs)
        updates=[];previous='NONE: ITERATION 1: DO NOT CONSIDER THIS'
        for batch in batches:
            phase='reasoning.'+article
            stage=original.ReasoningStage(request['facts'],'\n\n'.join(batch),article)
            previous=client.create(stage.get_stage_prompt(previous),temperature=0.,enable_thinking=False)
            updates.append(previous)
        outputs[article]=previous
        traces[article]=dict(issues=selected,issue_matches=matched,factors=selected_factors,guide_paragraph_ids=paragraph_ids,guide_paragraphs=paragraphs,updates=updates,prompt_history=prompt_history,response_history=response_history)
        tool('scale.issue_factor_guide_path',dict(article=article,**traces[article]))
    return dict(event='result',method='scale',output=outputs,paths=traces,calls=counter,source_commit=provenance['commit'],author_entry='StageProcessing(3,4) -> extract_paras -> extract_selected_paragraphs -> batch_paras -> ReasoningStage',prebuilt_author_hierarchy=True,original_model_weights_used=False,original_complete_benchmark=False,product_adaptation_completed=False)
if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=execute(request)
    emit(result)
