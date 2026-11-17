"""B01 original-controller replay and frozen-KIE text validation; AIPING <=100.
Source/original methods/benchmarks/I/O/adaptations are in product_adapter.py.
Native replay is not live 17-corpus validation; no reference answers enter messages.
"""
import argparse,asyncio,copy,hashlib,json,sqlite3,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT),str(HERE)]
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
from original_score import score as original_score
from screenshotlegal.method_reproductions.legalagentbench_bridge import request_for_task,benchmark_task
NAME='b01_legalagentbench'

async def main(track,variant,do_execute=False,replay_record=None):
    configuration=run.base.ReadOnlyConfiguration(ROOT/'product_v1/data')
    owner=configuration.get('model_configs',run.base.MODEL_ID)['owner_id']
    authorization=json.loads((run.OUT/'authorization.json').read_text(encoding='utf-8'))
    if authorization['limit_per_paper']!=100:raise ValueError('Existing paper cap changed')
    store=Store(run.OUT/'.runtime');benchmark=Benchmark(store)
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=run.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,100,authorization['historical_counts'])
    gateway.paper='B01';model=gateway.freeze(owner,run.base.MODEL_ID)
    evaluation={};lineage={};unit_cap=26
    if track=='native_replay':
        original=json.loads((HERE/'native_inputs/author_log_first_task.json').read_text(encoding='utf-8'))
        request=dict(mode='native_replay',variant=variant,question=original['question'],max_calls=unit_cap)
        entry=next(s for s in json.loads((HERE.parent/'sources.lock.json').read_text(encoding='utf-8')) if s['name']=='legalagentbench')
        data=json.loads((ROOT/entry['local_path']/'data/dataset.json').read_text(encoding='utf-8'))[0]
        evaluation=dict(reference=data,reference_labels_sent_to_model=False,scope='same task as original CLI; exact author-log tool observation replay only')
        lineage=dict(input_id=data['id'],selection='author CLI datas[0:1], not selected by performance',live_tool_service=False)
    elif track=='vqa_predicted_text':
        attempts=sorted([a for a in store.list('benchmark.attempt',owner) if a['status']=='completed' and not a.get('response',{}).get('demo') and (a.get('parsed') or {}).get('conversation')],key=lambda a:a['id'])
        upstream=attempts[0];dataset=benchmark.dataset(owner,upstream['dataset_id']);tasks=benchmark.load(dataset['tasks'])
        chosen=next(t for t in tasks if not t.get('region_id') and t.get('source_label')=='group_chat_or_private_chat')
        task=benchmark.freeze_task(owner,dataset['id'],chosen['task_id'],'vqa_predicted_text',upstream_id=upstream['id'])
        request=request_for_task(task['input'],variant,unit_cap)
        product_messages=[dict(role='system',content=DEFAULTS['vqa']),dict(role='user',content=json.dumps(task['input'],ensure_ascii=False))]
        evaluation=dict(task=task,reference=task['target'],reference_status=task['reference_status'])
        lineage=dict(upstream_attempt_id=upstream['id'],upstream_response_hash=digest(upstream['response']),selection='existing first frozen KIE attempt and group/private global question; no reference selection',source_context='frozen_predicted_KIE_only')
    else:
        db_path=ROOT/'paper/experiments/results/2026-10-28-deepseek-pilot/.runtime/research/research.sqlite3'
        with sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True) as db:frozen=json.loads(db.execute("SELECT body FROM records WHERE kind='agent.input' ORDER BY id LIMIT 1").fetchone()[0])
        visible=visible_input(frozen,'E23');request=dict(mode='case_product',variant=variant,input=visible,max_calls=unit_cap)
        lineage=dict(original_frozen_input_id=frozen['id'],selection='first previously authorized frozen case; no prior answer/Gold')
    pinned=next(s for s in json.loads((HERE.parent/'sources.lock.json').read_text(encoding='utf-8')) if s['name']=='legalagentbench')
    names=['paper/author_reproductions/legalagentbench/'+n for n in ('product_adapter.py','original_score.py','run_validation.py','requirements.lock.txt','native_inputs/author_log_first_task.json')]
    names += [pinned['local_path']+'/'+n for n in pinned['files']]
    names += ['product_v1/backend/src/screenshotlegal/method_reproductions/'+n for n in ('paper_bridge.py','author_bridge.py','legalagentbench_bridge.py','b01_legalagentbench.py','context.py')]
    replay=[]
    if replay_record:
        if track!='native_replay' or not replay_record.isalnum():raise ValueError('Only explicit native replay recovery is supported')
        previous=run.OUT/'methods'/NAME/'runs'/(replay_record+'__'+track+'__'+variant)
        original_input=json.loads((previous/(NAME+'.input.json')).read_text(encoding='utf-8'))
        if original_input['request']!=request:raise ValueError('Recovery request differs')
        model=original_input['plan']['model']  # Replay retains actual original model snapshot; it is not a new model run.
        replay=json.loads((previous/(NAME+'.model_responses.json')).read_text(encoding='utf-8'))
    names += ['product_v1/backend/src/screenshotlegal/experiments/'+n for n in ('engine.py','registry.py','contracts.py')]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(track=track,variant=variant,request=request,evaluation=evaluation,lineage=lineage,model=model,sources=hashes,replay_record=replay_record))[:16]
    directory=run.OUT/'methods'/NAME/'runs'/(plan_id+'__'+track+'__'+variant)
    plan=dict(plan_id=plan_id,created_at=now(),paper_id='B01',method=NAME,track=track,variant=variant,source_kind='author_source_controlled_tool_replay' if track=='native_replay' else 'author_source_with_product_tools',source_manifest=hashes,
        model=model,lineage=lineage,replay_record=replay_record,local_model_inference=False,maximum_additional_requests=0 if replay else unit_cap,cap_per_paper=100,original_complete_benchmark=False,expert_legal_gold_used=False)
    run.save(directory/(NAME+'.input.json'),dict(request=request,evaluation_only=evaluation,plan=plan))
    if not (directory/(NAME+'.provenance.json')).exists():run.save(directory/(NAME+'.provenance.json'),plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot')
        target=directory/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not do_execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,track=track,variant=variant,used=gateway.count('B01'),unit_cap=unit_cap)));store.close();return
    path=directory/(NAME+'.record.json')
    if path.exists():print(json.dumps(dict(status='existing_record_retained',path=str(path.relative_to(ROOT)))));store.close();return
    initial=gateway.count('B01')
    if not replay and initial+unit_cap>100:raise ValueError('Remaining shared paper budget cannot cover bounded unit')
    trace=[];tools=[];artifacts=[];checks={};output=None
    record=dict(paper_id='B01',method=NAME,track=track,variant=variant,plan_id=plan_id,status='running')
    run.save(path,record)
    async def raw(stage,messages,parameters):
        if gateway.count('B01')-initial>=unit_cap:raise ModelFailure('budget','Bounded paper unit exhausted')
        effective=copy.deepcopy(model);effective['parameters'].update(temperature=parameters['temperature'],max_tokens=parameters['max_tokens'])
        sid=plan_id+'.B01.'+track+'.'+stage
        item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=effective['parameters'],status='calling_model')
        trace.append(item);run.save(directory/(NAME+'.model_responses.json'),trace)
        if replay:
            old=replay[len(trace)-1]
            if old['stage']!=stage or old['messages']!=messages or old['original_parameters']!=parameters or old['status']!='completed':raise ValueError('Exact recovery response inputs differ; no API fallback')
            item.update(status='completed',response=old['response'],request_id=old['request_id'],replayed_from=replay_record)
            run.save(directory/(NAME+'.model_responses.json'),trace);return old['response']
        try:response=await gateway.call(owner,effective,messages,'paper_legalagentbench_'+track,sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));run.save(directory/(NAME+'.model_responses.json'),trace);raise
        item.update(status='completed',response=response);run.save(directory/(NAME+'.model_responses.json'),trace);return response
    async def tool(action,result):tools.append(dict(action=action,result=result));run.save(directory/(NAME+'.tools.json'),tools)
    async def artifact(name,result):artifacts.append(result);run.save(directory/(NAME+'.author_artifacts.json'),artifacts)
    async def case_tool(stage,name,args):await tool('legalagentbench.tool',args);return args
    async def generic(*args):raise ValueError('Old generic baseline must not execute')
    try:
        if track=='case_product':
            analysis=await run_method('E23',visible,frozen['sources'],generic,case_tool,SYSTEM_POLICY,lambda:{},dict(max_model_calls=unit_cap,legalagentbench_variant=variant),raw_call=raw,author_record=artifact)
            analysis=validate_output(analysis,frozen);result=artifacts[0]
        else:result=await execute('legalagentbench',request,raw,tool) if track=='native_replay' else await benchmark_task(product_messages,raw,tool,variant,unit_cap)
        if not result['controller_finished']:raise ValueError('Original controller did not reach Final Answer')
        if track=='native_replay':
            metrics=original_score(result['filtered_answer'],result['summary'],evaluation['reference'])
            output=dict(prediction=result['output'],execution=result,score=metrics)
            checks=dict(original_controller_finished=True,tool_observation_replayed=any(t['result']['mode']=='author_log_replay' for t in tools),
                reference_sent_to_model=False,live_service_validated=False,scope=evaluation['scope'],metrics=metrics)
        elif track=='vqa_predicted_text':
            value=result['output']
            output=dict(prediction=value,execution=result,score=benchmark_scoring.score(evaluation['task'],value,evaluation['reference'],evaluation['task']['asset']['width'],evaluation['task']['asset']['height']))
            checks=dict(product_schema_valid=True,evidence_ids_actually_read=True,reference_status=evaluation['reference_status'],score=output['score'],expert_accuracy=None)
        else:
            output=dict(prediction=analysis,execution=result,score=None)
            checks=dict(case_product_schema_valid=True,literal_citations_valid=True,legal_accuracy=None,tool_calls=len(tools))
        record.update(status='completed');checks.update(local_model_inference=False,original_complete_benchmark=False)
    except Exception as error:record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record['new_supplier_requests']=gateway.count('B01')-initial
        record['replayed_responses']=sum('replayed_from' in t for t in trace)
        record['per_paper_requests_including_history']=gateway.count('B01')
        run.save(path,record);run.save(directory/(NAME+'.output.json'),output)
        run.save(directory/(NAME+'.prompts.json'),[dict(stage=t['stage'],messages=t['messages']) for t in trace])
        run.save(directory/(NAME+'.tools.json'),tools)
        run.save(directory/(NAME+'.test_results.json'),dict(status=record['status'],checks=checks,original_complete_benchmark=False));store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,track=track,variant=variant,total_paper_requests=record['per_paper_requests_including_history'],path=str(directory.relative_to(ROOT))),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--track',choices=['native_replay','vqa_predicted_text','case_product'],required=True);p.add_argument('--variant',choices=['react','plan_and_solve','plan_and_execute'],default='react');p.add_argument('--execute',action='store_true');p.add_argument('--replay-record')
    a=p.parse_args();asyncio.run(main(a.track,a.variant,a.execute,a.replay_record))
