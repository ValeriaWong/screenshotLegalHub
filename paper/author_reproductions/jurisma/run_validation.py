"""L07 JurisMA inference-only validation; Lu et al., arXiv:2604.10470v1.
Degree/original method/innovation/benchmarks/I-O/adaptations: algorithm.py.
Native runs the exact Appendix C consultation illustration, not a LawBench test
record. Product runs frozen actual KIE text or a frozen case; no expert Gold.
All stages, graph/drafts/statute reads/prompts/replies/failures and source hashes
are retained. DPO/local checkpoints are deferred; author code is not claimed.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent
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
from screenshotlegal.method_reproductions.e18_jurisma import run_task
from screenshotlegal.experiments.engine import visible_input,SYSTEM_POLICY,validate_output

async def main(track,do_execute=False,reuse_from=None):
    configuration=run.base.ReadOnlyConfiguration(ROOT/'product_v1/data')
    owner=configuration.get('model_configs',run.base.MODEL_ID)['owner_id']
    authorization=json.loads((run.OUT/'authorization.json').read_text(encoding='utf-8'))
    if authorization['limit_per_paper']!=100:raise ValueError('Existing per-paper cap changed')
    store=Store(run.OUT/'.runtime');benchmark=Benchmark(store)
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=run.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,100,authorization['historical_counts'])
    gateway.paper='L07';model=gateway.freeze(owner,run.base.MODEL_ID)
    cached=[]
    if reuse_from:
        cached_folder=run.OUT/'methods/e18_jurisma/runs'/reuse_from
        cached_plan=json.loads((cached_folder/'e18_jurisma.provenance.json').read_text(encoding='utf-8'))
        def identity(snapshot):return {k:v for k,v in snapshot.items() if k not in ['id','created_at','credential_ref']}
        if identity(cached_plan['model'])!=identity(model):raise ValueError('Cached supplier/model/configuration changed')
        cached=json.loads((cached_folder/'e18_jurisma.model_responses.json').read_text(encoding='utf-8'))
    evaluation={};lineage={}
    if track=='native':
        original=json.loads((HERE/'native_inputs/paper_illustration.json').read_text(encoding='utf-8'))
        statutes=json.loads((HERE/'native_inputs/statutes.json').read_text(encoding='utf-8'))
        request=dict(question=original['question'],statutes=statutes,max_calls=28,policy='本文样例未提供全部航空录取审查依据；只将实际检索法源称为依据，缺失条件保留未知。')
        evaluation=dict(reference_status=original['reference_status'],expert_legal_accuracy=None)
        lineage=dict(input_provenance=original['provenance'],known_resource_gap=original['known_resource_gap'],exact_published_query=True)
    elif track=='vqa_predicted_text':
        attempts=sorted([a for a in store.list('benchmark.attempt',owner) if a['status']=='completed' and not a.get('response',{}).get('demo') and (a.get('parsed') or {}).get('conversation')],key=lambda a:a['id'])
        if not attempts:raise ValueError('No frozen actual KIE prediction')
        upstream=attempts[0];dataset=benchmark.dataset(owner,upstream['dataset_id'])
        tasks=benchmark.load(dataset['tasks'])
        candidates=sorted([t for t in tasks if t['task_family']!='kie.extract' and not t.get('region_id') and t['answer_kind']=='categorical' and t.get('allowed_values')],key=lambda t:(t.get('source_label',''),t['task_id']))
        task=benchmark.freeze_task(owner,dataset['id'],candidates[0]['task_id'],'vqa_predicted_text',upstream_id=upstream['id'])
        request=dict(messages=[dict(role='system',content=DEFAULTS['vqa']),dict(role='user',content=json.dumps(task['input'],ensure_ascii=False))])
        evaluation=dict(task=task,target=task['target'],reference_status=task['reference_status'])
        lineage=dict(upstream_attempt_id=upstream['id'],upstream_response_hash=digest(upstream['response']),source_context='frozen_KIE_prediction_only')
    else:
        path=ROOT/'paper/experiments/results/2026-10-28-deepseek-pilot/.runtime/research/research.sqlite3'
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            frozen=json.loads(db.execute("SELECT body FROM records WHERE kind='agent.input' ORDER BY id LIMIT 1").fetchone()[0])
        visible=visible_input(frozen,'E18')
        request=dict(input=visible)
        lineage=dict(original_frozen_input_id=frozen['id'],input_allowlist='visible_input(E18); no prior answer or expert Gold')
    if reuse_from:lineage['exact_request_cache_source']=reuse_from
    unit_cap=28 if track=='native' else 29
    names=['paper/author_reproductions/jurisma/'+n for n in ('algorithm.py','product_adapter.py','run_validation.py','specification.lock.json','paper_v1.html','prompts.json','algorithm_spec.json','requirements.lock.txt','environment_state.json','native_inputs/paper_illustration.json','native_inputs/statutes.json','native_inputs/amendment_viii.html','native_inputs/criminal_1997.html')]
    names+=['product_v1/backend/src/screenshotlegal/method_reproductions/'+n for n in ('e18_jurisma.py','jurisma_bridge.py','paper_bridge.py','author_bridge.py','context.py')]
    names+=['product_v1/backend/src/screenshotlegal/experiments/'+n for n in ('engine.py','registry.py')]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(track=track,request=request,evaluation=evaluation,lineage=lineage,model=model,sources=hashes))[:16]
    directory=run.OUT/'methods/e18_jurisma/runs'/(plan_id+'__'+track)
    plan=dict(plan_id=plan_id,created_at=now(),paper_id='L07',method='e18_jurisma',track=track,
        source_kind='paper_algorithm_inference_reimplementation_training_deferred',author_code_executed=False,source_manifest=hashes,
        model=model,lineage=lineage,local_model_inference=False,maximum_additional_requests=unit_cap,cap_per_paper=100,
        original_complete_benchmark=False,expert_legal_gold_used=False)
    run.save(directory/'e18_jurisma.input.json',dict(request=request,evaluation_only=evaluation,plan=plan))
    if not (directory/'e18_jurisma.provenance.json').exists():run.save(directory/'e18_jurisma.provenance.json',plan)
    for n,expected in hashes.items():
        data=(ROOT/n).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot: '+n)
        target=directory/'source_snapshot'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not do_execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,track=track,used=gateway.count('L07'),planned_requests=lineage.get('planned_requests'))));store.close();return
    record_path=directory/'e18_jurisma.record.json'
    if record_path.exists():
        print(json.dumps(dict(status='existing_record_retained',path=str(record_path.relative_to(ROOT)))));store.close();return
    initial=gateway.count('L07')
    if initial+unit_cap>100:raise ValueError('Shared budget cannot fund a bounded attempt')
    trace=[];artifacts=[];tools=[];checks={};output=None
    record=dict(paper_id='L07',method='e18_jurisma',track=track,plan_id=plan_id,status='running',source_kind='paper_algorithm_inference_reimplementation_training_deferred')
    run.save(record_path,record)
    async def raw(stage,messages,parameters):
        if gateway.count('L07')-initial>=unit_cap:raise ModelFailure('budget','Bounded unit cap reached')
        effective=copy.deepcopy(model);effective['parameters'].update(temperature=parameters['temperature'],max_tokens=parameters['max_tokens'])
        sid=plan_id+'.L07.'+track+'.'+stage
        item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=effective['parameters'],status='calling_model')
        exact=next((c for c in cached if c['stage']==stage and c['messages']==messages and c['original_parameters']==parameters and c.get('effective_parameters')==effective['parameters'] and c['status']=='completed' and c.get('response',{}).get('finish_reason')=='stop'),None)
        if exact:
            item.update(status='completed',response=copy.deepcopy(exact['response']),supplier_request_new=False,reused_request_id=exact['request_id'])
            trace.append(item);run.save(directory/'e18_jurisma.model_responses.json',trace)
            return item['response']
        item['supplier_request_new']=True
        trace.append(item);run.save(directory/'e18_jurisma.model_responses.json',trace)
        try:response=await gateway.call(owner,effective,messages,'paper_jurisma_'+track,sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));run.save(directory/'e18_jurisma.model_responses.json',trace);raise
        item.update(status='completed',response=response);run.save(directory/'e18_jurisma.model_responses.json',trace)
        return response
    async def artifact(name,result):artifacts.append(result);run.save(directory/'e18_jurisma.author_artifacts.json',artifacts)
    async def tool(action,result):tools.append(dict(action=action,result=result))
    async def generic(*args):raise ValueError('Old generic character worker path must not execute')
    try:
        if track=='native':
            result=await execute('jurisma',request,raw,tool)
            output=dict(native_output=result['output'],execution=result)
            checks=dict(published_consultation_query_executed=True,manager_rounds=len(result['iterations']),stop_reason=result['stop_reason'],maximum_rounds=5,content_check_executed=result['requests'][-1]['stage']=='content_check',retrieved_statutes=len(result['retrieved_statutes']),full_article_literal_checks=result['statutory_texts_literal_verified'],training_reproduced=False,native_full_method_completed=False,expert_legal_accuracy=None,complete_inference_algorithm_execution=True)
        elif track=='vqa_predicted_text':
            result=await run_task(request['messages'],raw,tool_trace=tool)
            output=dict(prediction=result['output'],execution=result,score=benchmark_scoring.score(evaluation['task'],result['output'],evaluation['target'],evaluation['task']['asset']['width'],evaluation['task']['asset']['height']))
            checks=dict(product_text_VQA_controller_completed=True,reference_status=evaluation['reference_status'],score=output['score'],source_context='frozen_predicted_KIE_only')
        else:
            output=await run_method('E18',visible,frozen['sources'],generic,generic,SYSTEM_POLICY,lambda:{},dict(max_model_calls=29),raw_call=raw,author_record=artifact)
            output=validate_output(output,frozen)
            result=artifacts[0]
            checks=dict(case_product_schema_valid=True,literal_citations_valid=True,product_projection_separate=True,native_full_method_completed=False,final_fact_count=len(output['facts']))
        record.update(status='completed')
        if track!='case_product':await artifact('jurisma',result)
        checks.update(native_full_method_completed=False,training_reproduced=False,local_model_inference=False,source_kind='paper_algorithm_inference_reimplementation_training_deferred',author_code_executed=False,expert_legal_accuracy=None)
    except Exception as error:
        record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record['new_supplier_requests']=gateway.count('L07')-initial
        record['reused_exact_responses']=sum(t.get('supplier_request_new') is False for t in trace)
        record['per_paper_requests_including_history']=gateway.count('L07')
        run.save(record_path,record);run.save(directory/'e18_jurisma.output.json',output)
        run.save(directory/'e18_jurisma.prompts.json',[dict(stage=t['stage'],messages=t['messages']) for t in trace])
        run.save(directory/'e18_jurisma.tools.json',tools)
        run.save(directory/'e18_jurisma.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,track=track,total_paper_requests=record['per_paper_requests_including_history'],path=str(directory.relative_to(ROOT))),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--track',choices=['native','vqa_predicted_text','case_product'],required=True);p.add_argument('--execute',action='store_true');p.add_argument('--reuse-from')
    a=p.parse_args();asyncio.run(main(a.track,a.execute,a.reuse_from))
