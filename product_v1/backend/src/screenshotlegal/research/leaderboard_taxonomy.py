"""Frozen-record classification; execution shape and paper provenance may overlap."""
from .contracts import digest

CATEGORIES=[
 dict(id='oneshot',label='单模型 One-shot',description='单模型直接作答；KIE 抽取子任务会明确标注，不等同 KIE 增强问答。',default_comparison='models'),
 dict(id='kie_enhanced',label='KIE 增强',description='实际消费 KIE 预测文本或预测消息区域的下游问答；原生抽取和整图对照不归入此类。',default_comparison='models'),
 dict(id='agent',label='Agent',description='工具循环、多阶段工作流、多角色、检索或分块协作。可与推断方法复现标签交叉。',default_comparison='methods'),
 dict(id='reproductions',label='推断方法复现',description='依据冻结的论文来源、作者控制器和复现级别归类；方法适配不等于原论文成绩复现。',default_comparison='methods'),
]
CATEGORY_IDS={c['id'] for c in CATEGORIES}
AGENT_IMPLEMENTATIONS={'controlled_tools','staged_no_pack','staged_with_pack','independent_context_verifier',
 'adversarial_review','neutral_judge','bounded_debate','factor_guided_retrieval','legal_r1_routing',
 'corrective_retrieval','chain_of_agents','jurisma_routing','scale_factor_hierarchy','verdict_collegial_review'}

AGENT_FAMILIES={'dynamic_agent','workflow','structured_legal_workflow','multi_agent_debate','dynamic_retrieval',
 'retrieval_correction','structured_dynamic','structured_legal_retrieval','iterative_verification'}

def method_info(run):
    m=run.get('method') or {'id':'E00'}
    baseline=m.get('id') in ['E00','E02','E03']
    agent=m.get('implementation') in AGENT_IMPLEMENTATIONS or m.get('family') in AGENT_FAMILIES or m.get('id') in ['E01','E02','E03']
    paper=not baseline and bool(m.get('author_controller') or m.get('paper_sources') or m.get('references') and m.get('reproduction_level'))
    return dict(id=m.get('id','unknown'),name=m.get('title') or m.get('name') or m.get('reproduction_name') or ('One-shot' if m.get('id')=='E00' else m.get('id','未知方法')),
        profile=digest(dict(method=m,options=run.get('method_options'),output_limit=run.get('method_max_output_tokens'))),
        agent=agent,paper=paper,reproduction_level=m.get('reproduction_level') or ('author_controller_adaptation' if m.get('author_controller') else 'project_baseline' if baseline else 'unverified'),
        original_paper_reproduced=m.get('original_paper_reproduced',m.get('original_benchmark_reproduced',False)),
        implementation_version=m.get('implementation_version'),implementation_digest=m.get('implementation_digest'),
        author_controller=m.get('author_controller'))

def categories(family,track,method):
    value=track if isinstance(track,str) else track.get('variant') or track.get('track')
    enhanced=value in ['reference_guided_prediction','vqa_predicted_text']
    result=[]
    if method['id']=='E00' and not enhanced:result.append('oneshot')
    if enhanced:result.append('kie_enhanced')
    if method['agent']:result.append('agent')
    if method['paper']:result.append('reproductions')
    return result

def entry_metadata(run,family,track,model):
    method=method_info(run)
    assigned=categories(family,track,method)
    name=('KIE → 问答 · '+method['name']) if 'kie_enhanced' in assigned else method['name']
    return dict(method=method,method_name=name,categories=assigned,
                entry_id=digest([model['identity'],method['profile']]),baseline=method['id']=='E00' and 'oneshot' in assigned,
                model_calls=(run.get('usage') or {}).get('model_calls',run.get('new_model_calls')),
                tool_calls=(run.get('usage') or {}).get('tool_calls'),input_tokens=(run.get('usage') or {}).get('input_tokens'),
                output_tokens=(run.get('usage') or {}).get('output_tokens'),elapsed_ms=(run.get('usage') or {}).get('elapsed_ms'))

def comparison_definition(definition,model,comparison):
    value=dict(definition)
    if comparison=='methods':
        # Method-specific controllers/prompts are the treatment. Base input, base
        # prompt, scorer, budget and exact bottom-model configuration stay fixed.
        value['comparison']='methods'
        value.pop('method',None)
        value['fixed_model']=dict(identity=model['identity'],model=model['model'])
    return value
