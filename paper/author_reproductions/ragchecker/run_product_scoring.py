"""B15 RAGChecker: evaluate existing frozen KIE/text-global-VQA product attempts.
Author source, innovation, original I/O and fidelity: product_adapter.py.
No producer rerun: judge-only calls count against the same B15 <=100 durable cap.
Native and product, failed/unknown/history share it. No fabricated KIE transcript,
no pixel/legal-accuracy claim, no overwrite of primary scores or previous attempts.
"""
import argparse,asyncio,copy,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as base
from screenshotlegal.research.store import Store
from screenshotlegal.research.benchmark import Benchmark
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.research.gateway import ModelFailure,error_view

async def main(do_execute=False):
    configuration=base.base.ReadOnlyConfiguration(ROOT/'product_v1/data');owner=configuration.get('model_configs',base.base.MODEL_ID)['owner_id']
    auth=json.loads((base.OUT/'authorization.json').read_text(encoding='utf-8'))
    if auth['limit_per_paper']!=100:raise PermissionError('Paper cap cannot reset')
    store=Store(base.OUT/'.runtime');benchmark=Benchmark(store)
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=base.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,100,auth['historical_counts']);gateway.paper='B15'
    model=gateway.freeze(owner,base.base.MODEL_ID);selected={}
    for attempt in sorted(store.list('benchmark.attempt',owner),key=lambda r:r['id']):
        if attempt['status']!='completed' or attempt.get('response',{}).get('demo') or attempt.get('pipeline_id'):continue
        run=store.get('benchmark.run',attempt['run_id'],owner);track=run['track']
        if track not in ['kie_image','vqa_predicted_text'] or track in selected:continue
        task=next(t for t in run['tasks'] if t['task_id']==attempt['task_id'])
        primary=next((s for s in store.list('benchmark.score',owner) if s['attempt_id']==attempt['id'] and 'target_snapshot' in s),None)
        if primary:selected[track]=(attempt,run,task,primary)
    if set(selected)!={'kie_image','vqa_predicted_text'}:raise ValueError('Both real frozen product attempt tracks and primary references are required')
    names=['paper/author_reproductions/ragchecker/'+n for n in ['product_adapter.py','run_product_scoring.py','requirements.lock.txt']]
    names+=['product_v1/backend/src/screenshotlegal/'+n for n in ['method_reproductions/b15_ragchecker.py','method_reproductions/author_bridge.py','research/ragchecker_scoring.py','research/benchmark.py','research/benchmark_scoring.py']]
    names+=['paper/author_reproductions/author_runtime.py']
    for pin in json.loads((HERE.parent/'sources.lock.json').read_text(encoding='utf-8')):
        if pin['name'] in ['ragchecker','refchecker']:names += [pin['local_path']+'/'+n for n in pin['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    records=[]
    try:
        for track in ['kie_image','vqa_predicted_text']:
            attempt,run,task,primary=selected[track];unit_cap=20
            plan_id=digest(dict(track=track,attempt=attempt,task=task,primary=primary,model=model,sources=hashes))[:16]
            directory=base.OUT/'methods/b15_ragchecker/runs'/(plan_id+'__product_scoring_'+track)
            plan=dict(plan_id=plan_id,created_at=now(),paper_id='B15',method='b15_ragchecker',track='product_scoring_'+track,
                source_manifest=hashes,model=model,maximum_additional_requests=unit_cap,limit_per_paper=100,
                original_attempt_id=attempt['id'],primary_score_id=primary['id'],selection='lexicographically first completed real attempt with frozen primary target per track',
                producer_rerun=False,expert_legal_gold_used=False,original_complete_benchmark=False,local_model_inference=False)
            base.save(directory/'b15_ragchecker.provenance.json',plan)
            base.save(directory/'b15_ragchecker.input.json',dict(task=task,original_input=task['input'],model_response=attempt['response'],frozen_primary_score=primary,plan=plan))
            for name,expected in hashes.items():
                data=(ROOT/name).read_bytes()
                if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot')
                target=directory/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            if not do_execute:records.append(dict(plan_id=plan_id,status='planned',track=track));continue
            record_path=directory/'b15_ragchecker.record.json'
            if record_path.exists():records.append(json.loads(record_path.read_text(encoding='utf-8')));continue
            initial=gateway.count('B15')
            if initial+unit_cap>100:raise ModelFailure('budget','Insufficient shared B15 budget for bounded product scoring')
            trace=[];tools=[];checks={};output=None
            record=dict(paper_id='B15',method='b15_ragchecker',track=plan['track'],status='running',plan_id=plan_id)
            base.save(record_path,record)
            async def raw_call(stage,messages,parameters):
                if gateway.count('B15')-initial>=unit_cap:raise ModelFailure('budget','RAGChecker product unit cap reached')
                current=copy.deepcopy(model);current['parameters'].update(temperature=0,max_tokens=parameters['max_new_tokens'])
                sid=plan_id+'.B15.'+track+'.'+stage
                item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=current['parameters'],status='calling_model')
                trace.append(item);base.save(directory/'b15_ragchecker.model_responses.json',trace)
                try:response=await gateway.call(owner,current,messages,'ragchecker_product_scoring',sid)
                except Exception as error:
                    item.update(status='failed',error=error_view(error));base.save(directory/'b15_ragchecker.model_responses.json',trace);raise
                item.update(status='completed',response=response);base.save(directory/'b15_ragchecker.model_responses.json',trace);return response
            async def author_record(action,result):
                tools.append(dict(action=action,result=result));base.save(directory/'b15_ragchecker.tools.json',tools)
            try:
                output=await benchmark.ragchecker_score(owner,attempt['id'],dict(idempotency_key='b15.'+plan_id),raw_call,author_record)
                result=output['result'];execution=result.get('author_execution',{})
                checks=dict(product_dispatch_executed=True,score_status=result['status'],reference_status=output['reference_status'],
                    primary_score_unchanged=store.get('benchmark.score',primary['id'],owner)==primary,original_attempt_unchanged=store.get('benchmark.attempt',attempt['id'],owner)==attempt,
                    original_author_checks=execution.get('checks'),missing_gold_not_fabricated=True,
                    full_product_track_completed=result['status']=='scored',expert_legal_accuracy=None,local_model_inference=False)
                record.update(status='completed')
            except Exception as error:record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
            finally:
                record.update(new_supplier_requests=gateway.count('B15')-initial,per_paper_requests_including_history=gateway.count('B15'))
                base.save(record_path,record);base.save(directory/'b15_ragchecker.output.json',output);base.save(directory/'b15_ragchecker.tools.json',tools)
                base.save(directory/'b15_ragchecker.model_responses.json',trace);base.save(directory/'b15_ragchecker.prompts.json',[dict(stage=r['stage'],messages=r['messages']) for r in trace])
                base.save(directory/'b15_ragchecker.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
            records.append(record)
    finally:store.close()
    print(json.dumps(dict(records=records,used=records[-1].get('per_paper_requests_including_history'))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args();asyncio.run(main(a.execute))
