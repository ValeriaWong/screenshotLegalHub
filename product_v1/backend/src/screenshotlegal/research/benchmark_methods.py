"""Author method dispatch for frozen KIE/image/text VQA tasks."""
import copy
import hashlib
import json
from pathlib import Path
from .contracts import digest,now,dumps
from .gateway import ModelFailure,error_view,author_inference_parameters
from screenshotlegal.method_reproductions.author_bridge import REPO,self_refine_environment

STEP='benchmark.method_step'

def specification(method,attempts=2,protocol='hybrid',variant='react'):
    names={'E25':'l06_legal_reasoning_paths','E24':'r04_graphrag','E00':'e00_single_shot','E01':'e01_react','E05':'e05_self_refine',
           'E18':'e18_jurisma','E23':'b01_legalagentbench','E09':'e09_l_mad','E14':'e14_chain_of_agents','E15':'e15_raptor','E16':'e16_lightrag','E21':'e21_reflexion'}
    if method not in names:raise ValueError('当前KIE/VQA作者方法入口未接入该方法')
    if attempts not in [1,2,3]:raise ValueError('迭代次数必须为1至3')
    if method=='E23' and variant not in ['react','plan_and_solve','plan_and_execute']:raise ValueError('LegalAgentBench controller variant unsupported')
    calls={'E25':20,'E24':40,'E18':29,'E23':4 if variant=='plan_and_solve' else 6,'E00':1,'E01':14,'E05':2*attempts,'E09':24 if protocol=='ranked' else 10,'E14':2,'E15':1,'E16':4,'E21':3*attempts-1}[method]
    result=dict(id=method,name=names[method],calls_per_task=calls,attempts=attempts,original_benchmark_reproduced=False)
    if method in ['E09','E14','E15','E16','E18','E23','E24','E25']:result['dynamic_call_budget']=True
    if method=='E23':result.update(variant=variant,source_kind='author_source_with_product_tools',original_live_corpora_available=False)
    if method=='E09':
        if protocol not in ['hybrid','ranked']:raise ValueError('L-MAD protocol unsupported')
        result.update(protocol=protocol,discussion_rounds=3,source_kind='paper_specification_with_cited_upstream_components',LMAD_author_code_executed=False)
    if method=='E25':result.update(source_kind='paper_pipeline_reimplementation_with_author_prompts_ontology',author_code_executed=False,embedding_retrieval_executed=False,native_full_method_completed=False)
    if method=='E18':result.update(source_kind='paper_algorithm_inference_reimplementation_training_deferred',author_code_executed=False,native_full_method_completed=False)
    if method=='E14':result.update(source_kind='paper_algorithm_reimplementation',author_code_executed=False)
    if method!='E00':
        from screenshotlegal.method_reproductions.author_bridge import source_manifest
        if method=='E01':
            from screenshotlegal.method_reproductions.react_bridge import environment
            _,driver=environment()
        elif method=='E05':_,driver=self_refine_environment()
        else:
            from screenshotlegal.method_reproductions.paper_bridge import environment
            _,driver=environment({'E25':'legal_reasoning_paths','E24':'graphrag','E18':'jurisma','E23':'legalagentbench','E09':'l_mad','E14':'chain_of_agents','E15':'raptor','E16':'lightrag','E21':'reflexion'}[method])
        files=[driver,Path(__file__),REPO/'product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py',
               REPO/('product_v1/backend/src/screenshotlegal/method_reproductions/'+names[method]+'.py'),
               REPO/'paper/author_reproductions/sources.lock.json']
        controllers={'E25':'L06 exact author prompts + scoped-history typed RDF pipeline reimplementation; embedding retrieval pending','E24':'GraphRAG v0.1.1 original index workflows (no embeddings) + GlobalSearch.asearch','E18':'JurisMA §§3.2–3.4/Algorithm 1 inference only; training deferred','E23':'LegalAgentBench '+variant+' pinned original controller with frozen text tools','E01':'hotpotqa.ipynb:webthink','E05':'src/responsegen/run.py:iterative_response',
                     'E09':'LMAD paper scheduler + cited MALLM threshold/ranked components',
                     'E14':'CoA paper Algorithm 1 (our reimplementation), Tables 9/10',
                     'E15':'ClusterTreeBuilder.construct_tree + TreeRetriever.retrieve',
                     'E16':'operate.extract_entities + operate.kg_query','E21':'CoTAgent.run/step/reflect'}
        result.update(author_sources=source_manifest(),author_controller=controllers[method],
                      adapter_sha256={p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    return result

async def execute(benchmark,owner,run,task,attempt,messages,alive,checkpoint):
    method=run['method'];store=benchmark.store
    if specification(method['id'],method['attempts'],method.get('protocol','hybrid'),method.get('variant','react'))!=method:raise ValueError('作者适配代码已变化，请新建运行；不使用旧计划调用新代码')
    responses=[]
    def accepted(response):
        if not response.get('demo') and not all(isinstance((response.get('usage') or {}).get(k),int) for k in ['prompt_tokens','completion_tokens']):
            raise ModelFailure('usage_missing','供应商用量缺失，停止作者控制器后续调用；原响应已保存')
        responses.append(response)
        return response
    async def call(stage,forwarded,original_parameters):
        await alive()
        sid=attempt['id']+':'+stage
        old=store.optional(STEP,sid,owner)
        if old:
            if old['status']=='completed':return accepted(old['response'])
            request=store.optional('evaluation.request',sid,owner)
            if request and request['status']=='completed':
                old.update(status='completed',response=request['response'],recovered_gateway_response=True,finished_at=now())
                with store.tx() as db:store.put(STEP,old,owner,db)
                return accepted(old['response'])
            raise ModelFailure('previous_call_unresolved','作者方法此步骤已有失败或未知调用，不自动重发',False,old['status']=='calling_model')
        model=copy.deepcopy(run['model'])
        model['parameters']=author_inference_parameters(model)
        model['parameters']['max_tokens']=min(run['method_max_output_tokens'],1024 if stage.startswith('feedback.') else run['method_max_output_tokens'])
        if method['id']=='E01':
            stops=original_parameters.get('stop') or []
            if isinstance(stops,str):stops=[stops]
            model['parameters']['stop']=list(dict.fromkeys([*stops,'\nObservation']))
        if method['id']=='E15' and stage.startswith('summary.'):
            model['parameters']['max_tokens']=min(model['parameters']['max_tokens'],original_parameters.get('max_tokens',100))
        if method['id'] in ['E09','E14','E18','E23','E24','E25']:
            model['parameters']['max_tokens']=min(model['parameters']['max_tokens'],original_parameters['max_tokens'])
            model['parameters']['temperature']=original_parameters['temperature']
        if method['id'] in ['E24','E25']:
            for key in ['top_p','frequency_penalty','presence_penalty','response_format','stop']:
                if key in original_parameters:model['parameters'][key]=original_parameters[key]
        row=dict(id=sid,run_id=run['id'],attempt_id=attempt['id'],task_id=task['task_id'],method_id=method['id'],reproduction_name=method['name'],stage=stage,status='calling_model',messages=forwarded,input_hash=digest(forwarded),original_parameters=original_parameters,effective_parameters=model['parameters'],created_at=now())
        with store.tx() as db:
            prior=[s for s in store.list(STEP,owner,db) if s['run_id']==run['id']]
            if len(prior)>=run['max_calls']:raise ModelFailure('budget','本轮作者方法调用上限已用完；不发送后续请求')
            store.put(STEP,row,owner,db)
        await checkpoint('method-start:'+sid,sid,'calling_model')
        try:
            if model['config_id']=='demo':
                value=dict(dialog_name=None,conversation=[]) if task['task_family']=='kie.extract' else dict(answer=None,evidence=[])
                raw=('核对原图\nAction 1: Finish['+dumps(value)+']') if method['id']=='E01' else ('Scores:\nIssues: 离线传输检查\nTotal score: 0/25' if stage.startswith('feedback.') else dumps(value))
                if method['id'] in ['E24','E25']:
                    from importlib import import_module
                    demo_reply=import_module('screenshotlegal.method_reproductions.'+('graphrag_bridge' if method['id']=='E24' else 'legal_reasoning_paths_bridge')).demo_reply
                    raw=demo_reply(stage,forwarded,value)
                if method['id']=='E18':
                    from screenshotlegal.method_reproductions.jurisma_bridge import demo_reply
                    raw=demo_reply(stage,value)
                if method['id']=='E23':
                    from screenshotlegal.method_reproductions.legalagentbench_bridge import demo_reply
                    raw=demo_reply(stage,value,'kie:'+task['input']['upstream_sha256'])
                if method['id']=='E09':raw='0 1 2' if '.vote.' in stage else '[AGREE]\nAnswer:Y'
                if method['id']=='E21':raw=('核对输入' if stage.startswith('label.') else '修正输出结构' if stage.startswith('reflection.') else 'Finish['+dumps(value)+']')
                if method['id']=='E16':
                    raw=(dumps(dict(high_level_keywords=['materials'],low_level_keywords=['FROZEN SOURCE'])) if stage.startswith('keywords.') else
                         '("entity"<|>"FROZEN SOURCE"<|>"CONCEPT"<|>"Offline transport source")##("entity"<|>"MATERIAL"<|>"CONCEPT"<|>"Offline input")##("relationship"<|>"FROZEN SOURCE"<|>"MATERIAL"<|>"Offline transport link"<|>"materials"<|>1)<|COMPLETE|>' if stage.startswith('index.') else dumps(value))
                response=dict(raw=raw,demo=True,usage=None,cost_estimate=0,cost_currency='CNY',latency_ms=0)
            else:
                response=await benchmark.gateway.call(owner,model,forwarded,'benchmark_author_method',sid)
            row.update(status='completed',response=response,finished_at=now())
        except Exception as error:
            view=error_view(error);row.update(status='unknown' if view.get('unknown') else 'failed',error=view,finished_at=now())
            with store.tx() as db:store.put(STEP,row,owner,db)
            raise
        with store.tx() as db:store.put(STEP,row,owner,db)
        await checkpoint('method-response:'+sid,sid,'response_saved')
        return accepted(response)
    tool_count=0
    async def tool_trace(action,result):
        nonlocal tool_count
        await alive()
        tid=attempt['id']+':tool:'+str(tool_count);tool_count+=1
        old=store.optional('benchmark.method_tool',tid,owner)
        if old:
            if old['action']!=action or old['result']!=result:raise ValueError('恢复后的工具轨迹与已冻结记录不一致')
            return
        row=dict(id=tid,run_id=run['id'],attempt_id=attempt['id'],task_id=task['task_id'],reproduction_name=method['name'],action=action,result=result,created_at=now())
        with store.tx() as db:store.put('benchmark.method_tool',row,owner,db,immutable=True)
    from screenshotlegal.method_reproductions.catalog import method_module
    try:
        if method['id']=='E23':result=await method_module(method['id']).run_task(messages,call,method['attempts'],tool_trace=tool_trace,variant=method['variant'])
        elif method['id']=='E09':result=await method_module(method['id']).run_task(messages,call,method['attempts'],tool_trace=tool_trace,protocol=method['protocol'])
        else:result=await method_module(method['id']).run_task(messages,call,method['attempts'],tool_trace=tool_trace)
    except ValueError as error:
        raise ModelFailure('author_controller',str(error)) from error
    usage=None if any(r.get('usage') is None for r in responses) else {k:sum(r['usage'].get(k,0) for r in responses) for k in ['prompt_tokens','completion_tokens','total_tokens']}
    costs=[r.get('cost_estimate') for r in responses]
    return dict(raw=dumps(result['output']),native_final_response=responses[-2 if method['id']=='E05' else -1]['raw'],demo=run['model']['config_id']=='demo',usage=usage,cost_estimate=sum(costs) if all(c is not None for c in costs) else None,cost_currency=responses[0].get('cost_currency'),latency_ms=sum(r.get('latency_ms',0) for r in responses),response_models=sorted({r['response_model'] for r in responses if r.get('response_model')}),request_ids=[s['id'] for s in store.list(STEP,owner) if s['attempt_id']==attempt['id']],author_execution=result)
