"""L06 real author-prompt trials; all history/failures/inflight share <=100.
Source/innovation/benchmark/I/O/adaptation degree are at the top of algorithm.py.
Author Python code was not released; full embedding retrieval is NOT reproduced.
Default plans only; --execute is needed for real authorized DeepSeek requests.
"""
import argparse,asyncio,copy,hashlib,json,sqlite3,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT),str(HERE.parent)]
from paper.author_reproductions import run_per_paper_validation as run
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.store import Store
from screenshotlegal.research.benchmark import Benchmark,DEFAULTS
from screenshotlegal.research import benchmark_scoring
from screenshotlegal.research.gateway import error_view,ModelFailure
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.method_reproductions.paper_bridge import execute
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.experiments.engine import visible_input,SYSTEM_POLICY,validate_output
METHOD='l06_legal_reasoning_paths';PAPER='L06'
SOURCE_KIND='paper_pipeline_reimplementation_with_author_prompts_ontology'

async def main(track,do_execute=False,reuse_completed=None):
    configuration=run.base.ReadOnlyConfiguration(ROOT/'product_v1/data')
    owner=configuration.get('model_configs',run.base.MODEL_ID)['owner_id']
    authorization=json.loads((run.OUT/'authorization.json').read_text(encoding='utf-8'))
    if authorization['limit_per_paper']!=100:raise ValueError('Shared authorization changed')
    store=Store(run.OUT/'.runtime');benchmark=Benchmark(store)
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=run.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,100,authorization['historical_counts'])
    gateway.paper=PAPER;model=gateway.freeze(owner,run.base.MODEL_ID)
    evaluation={};lineage={}
    if track=='native':
        fixture=json.loads((HERE/'native_input.json').read_text(encoding='utf-8'))
        request=fixture['request'];evaluation=fixture['evaluation_only'];lineage=fixture['lineage'];unit_cap=35
    elif track=='vqa_predicted_text':
        attempts=sorted([a for a in store.list('benchmark.attempt',owner) if a['status']=='completed' and not a.get('response',{}).get('demo') and (a.get('parsed') or {}).get('conversation')],key=lambda a:a['id'])
        upstream=attempts[0];dataset=benchmark.dataset(owner,upstream['dataset_id']);tasks=benchmark.load(dataset['tasks'])
        candidates=sorted([t for t in tasks if t['task_family']!='kie.extract' and not t.get('region_id') and t['answer_kind']=='categorical' and t.get('allowed_values')],key=lambda t:(t.get('source_label',''),t['task_id']))
        task=benchmark.freeze_task(owner,dataset['id'],candidates[0]['task_id'],'vqa_predicted_text',upstream_id=upstream['id'])
        request=dict(messages=[dict(role='system',content=DEFAULTS['vqa']),dict(role='user',content=json.dumps(task['input'],ensure_ascii=False))])
        evaluation=dict(task=task,target=task['target'],reference_status=task['reference_status'])
        lineage=dict(upstream_attempt_id=upstream['id'],upstream_response_hash=digest(upstream['response']),source_context='frozen_KIE_prediction_only');unit_cap=20
    else:
        database=ROOT/'paper/experiments/results/2026-10-28-deepseek-pilot/.runtime/research/research.sqlite3'
        with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
            frozen=json.loads(db.execute("SELECT body FROM records WHERE kind='agent.input' ORDER BY id LIMIT 1").fetchone()[0])
        visible=visible_input(frozen,'E25');request=dict(input=visible)
        lineage=dict(original_frozen_input_id=frozen['id'],input_allowlist='visible_input(E25); no old output or expert Gold');unit_cap=25
    names=['paper/author_reproductions/legal_reasoning_paths/'+n for n in ['algorithm.py','product_adapter.py','run_validation.py','requirements.lock.txt','environment_state.json','native_input.json']]
    names+=['paper/author_reproductions/author_runtime.py','paper/author_reproductions/run_per_paper_validation.py','paper/author_reproductions/sources.lock.json','product_v1/backend/src/screenshotlegal/research/gateway.py','product_v1/backend/src/screenshotlegal/method_reproductions/paper_bridge.py','product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py']
    for name in ['l06_legal_reasoning_paths.py','legal_reasoning_paths_bridge.py']:
        p='product_v1/backend/src/screenshotlegal/method_reproductions/'+name
        if (ROOT/p).exists():names.append(p)
    source=next(s for s in json.loads((HERE.parent/'sources.lock.json').read_text(encoding='utf-8')) if s['name']=='legal_reasoning_paths')
    names += [source['local_path']+'/'+n for n in source['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(track=track,request=request,evaluation=evaluation,lineage=lineage,model=model,sources=hashes))[:16]
    directory=run.OUT/'methods'/METHOD/'runs'/(plan_id+'__'+track)
    plan=dict(plan_id=plan_id,created_at=now(),paper_id=PAPER,method=METHOD,track=track,source_kind=SOURCE_KIND,source_manifest=hashes,model=model,lineage=lineage,maximum_additional_requests=unit_cap,cap_per_paper=100,local_model_inference=False,embedding_retrieval_executed=False,original_complete_benchmark=False,expert_legal_gold_used=False)
    run.save(directory/(METHOD+'.input.json'),dict(request=request,evaluation_only=evaluation,plan=plan));run.save(directory/(METHOD+'.provenance.json'),plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot: '+name)
        target=directory/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not do_execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,track=track,used=gateway.count(PAPER),maximum_additional_requests=unit_cap)));store.close();return
    record_path=directory/(METHOD+'.record.json')
    if record_path.exists():raise ValueError('Existing attempt retained; do not rerun it')
    initial=gateway.count(PAPER)
    if initial+unit_cap>100:raise ValueError('Remaining shared paper budget cannot fund this bounded unit')
    record=dict(paper_id=PAPER,method=METHOD,track=track,plan_id=plan_id,status='running',source_kind=SOURCE_KIND);run.save(record_path,record)
    cache={}
    if reuse_completed:
        if track!='native' or not all(c in '0123456789abcdef' for c in reuse_completed) or len(reuse_completed)!=16:raise ValueError('Only explicit same-paper native plan reuse is accepted')
        previous=run.OUT/'methods'/METHOD/'runs'/(reuse_completed+'__native')
        provenance=json.loads((previous/(METHOD+'.provenance.json')).read_text(encoding='utf-8'))
        if provenance['model']!=model:raise ValueError('Cached model snapshot differs')
        rows=json.loads((previous/(METHOD+'.model_responses.json')).read_text(encoding='utf-8'))
        cache={r['stage']:r for r in rows if r['status']=='completed' and r.get('response',{}).get('finish_reason')=='stop'}
    trace=[];tools=[];artifacts=[];output=None;checks={}
    async def raw(stage,messages,parameters):
        if gateway.count(PAPER)-initial>=unit_cap:raise ModelFailure('budget','Bounded unit exhausted')
        effective=copy.deepcopy(model)
        for key in ['temperature','max_tokens','top_p','frequency_penalty','presence_penalty','response_format','stop']:
            if key in parameters:effective['parameters'][key]=parameters[key]
        sid=plan_id+'.L06.'+track+'.'+stage
        if not sid.isascii():raise ValueError('HTTP request IDs must be ASCII')
        cached=cache.get(stage)
        if cached:
            if cached['messages']!=messages or cached['effective_parameters']!=effective['parameters']:raise ValueError('Explicit cache input/parameters differ; no resend')
            item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=effective['parameters'],status='completed',supplier_request_new=False,reused_from_plan_id=reuse_completed,reused_from_request_id=cached['request_id'],response=cached['response'])
            trace.append(item);run.save(directory/(METHOD+'.model_responses.json'),trace);return cached['response']
        item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=effective['parameters'],status='calling_model',supplier_request_new=True)
        trace.append(item);run.save(directory/(METHOD+'.model_responses.json'),trace)
        try:
            response=await gateway.call(owner,effective,messages,'paper_legal_reasoning_paths_'+track,sid)
            item.update(status='completed',response=response);run.save(directory/(METHOD+'.model_responses.json'),trace)
            if response.get('finish_reason')!='stop':raise ModelFailure('output_limit','Actual reply incomplete; no automatic paid retry')
            return response
        except Exception as error:
            item.update(status='failed',error=error_view(error));run.save(directory/(METHOD+'.model_responses.json'),trace);raise
    async def tool(action,result):
        tools.append(dict(action=action,result=result));run.save(directory/(METHOD+'.tools.json'),tools)
    async def artifact(name,result):
        if result.get('observations'):tools.extend(result['observations']);run.save(directory/(METHOD+'.tools.json'),tools)
        artifacts.append(result);run.save(directory/(METHOD+'.author_artifacts.json'),artifacts)
    async def forbidden(*a):raise ValueError('Generic prototype path must not execute')
    try:
        if track=='native':
            result=await execute('legal_reasoning_paths',request,raw,tool)
            output=dict(native_output=result['output'],execution=result,author_saved_prediction_comparison={t['stage']:t['output']==evaluation['author_saved_predictions'][t['stage']] for t in result['exact_author_fixture']})
            checks=dict(native_original_three_prompts_executed=len(result['exact_author_fixture'])==3,pipeline_reimplementation_executed=True,original_text_sections=2,author_saved_predictions_are_not_gold=True)
        elif track=='vqa_predicted_text':
            from screenshotlegal.method_reproductions.l06_legal_reasoning_paths import run_task
            result=await run_task(request['messages'],raw,tool_trace=tool)
            output=dict(prediction=result['output'],execution=result,score=benchmark_scoring.score(evaluation['task'],result['output'],evaluation['target'],evaluation['task']['asset']['width'],evaluation['task']['asset']['height']))
            checks=dict(product_text_VQA_controller_completed=True,reference_status=evaluation['reference_status'],score=output['score'],source_context='frozen_predicted_KIE_only')
        else:
            output=await run_method('E25',visible,frozen['sources'],forbidden,forbidden,SYSTEM_POLICY,lambda:{},dict(max_model_calls=25),raw_call=raw,author_record=artifact)
            output=validate_output(output,frozen);result=artifacts[0]
            checks=dict(case_product_schema_valid=True,literal_citations_valid=True,final_fact_count=len(output['facts']))
        if any(t['status']!='completed' for t in trace):raise ValueError('Transport failure swallowed by pipeline')
        if track!='case_product':await artifact('legal_reasoning_paths',result)
        checks.update(result['checks'],author_code_executed=False,author_prompts_used=True,local_model_inference=False,neural_modules_loaded=result['neural_modules_loaded'],expert_legal_accuracy=None,source_kind=SOURCE_KIND,embedding_retrieval_executed=False,existing_path_count=len(result['existing_graph_paths']),stage_names=[s['stage'] for s in result['stages']])
        record.update(status='completed')
    except Exception as error:
        record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record.update(new_supplier_requests=gateway.count(PAPER)-initial,per_paper_requests_including_history=gateway.count(PAPER))
        run.save(record_path,record);run.save(directory/(METHOD+'.output.json'),output)
        run.save(directory/(METHOD+'.prompts.json'),[dict(stage=t['stage'],messages=t['messages']) for t in trace]);run.save(directory/(METHOD+'.tools.json'),tools)
        run.save(directory/(METHOD+'.test_results.json'),dict(status=record['status'],checks=checks,original_complete_benchmark=False));store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,track=track,total_paper_requests=record['per_paper_requests_including_history'],new_requests=record['new_supplier_requests'],path=str(directory.relative_to(ROOT))),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--track',choices=['native','vqa_predicted_text','case_product'],required=True);p.add_argument('--execute',action='store_true');p.add_argument('--reuse-completed')
    a=p.parse_args();asyncio.run(main(a.track,a.execute,a.reuse_completed))
