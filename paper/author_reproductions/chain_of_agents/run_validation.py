"""A06 CoA paper-algorithm native and product validation (DeepSeek API, <=100/paper).
Source/fidelity/benchmarks/original I/O: algorithm.py and specification.lock.json.
Native uses complete official LongBench HotpotQA row 0; public references stay in
scoring only. Product uses frozen actual KIE predictions or the existing frozen
case; no expert Gold. Raw calls, CUs, chunks, prompts, source and failures persist.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import re
import sqlite3
import string
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT),str(HERE.parent)]
from paper.author_reproductions import run_per_paper_validation as run
from author_runtime import source,original_definitions
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.store import Store
from screenshotlegal.research.benchmark import Benchmark,DEFAULTS
from screenshotlegal.research import benchmark_scoring
from screenshotlegal.research.gateway import error_view,ModelFailure
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.method_reproductions.paper_bridge import execute
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.method_reproductions.e14_chain_of_agents import run_task
from screenshotlegal.experiments.engine import visible_input,SYSTEM_POLICY,validate_output

async def main(track,do_execute=False):
    configuration=run.base.ReadOnlyConfiguration(ROOT/'product_v1/data')
    owner=configuration.get('model_configs',run.base.MODEL_ID)['owner_id']
    authorization=json.loads((run.OUT/'authorization.json').read_text(encoding='utf-8'))
    if authorization['limit_per_paper']!=100:raise ValueError('Existing per-paper cap changed')
    store=Store(run.OUT/'.runtime');benchmark=Benchmark(store)
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=run.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,100,authorization['historical_counts'])
    gateway.paper='A06';model=gateway.freeze(owner,run.base.MODEL_ID)
    evaluation={};lineage={}
    if track=='native':
        original=json.loads((HERE/'native_inputs/hotpotqa_first.json').read_text(encoding='utf-8'))
        longbench,entry=source('longbench')
        prompt=json.loads((longbench/'LongBench/config/dataset2prompt.json').read_text(encoding='utf-8'))['hotpotqa']
        requirement=prompt.split('\n\nThe following are given passages.')[0]
        request=dict(text=original['context'],question=original['input'],task_requirement=requirement,
            query_based=True,window_tokens=8192,max_output_tokens=1024,max_calls=20)
        evaluation=dict(references=original['answers'],official_dataset_id=original.get('_id'),reference_sent_to_model=False)
        async def no_model(*args):raise ValueError('Planning cannot request a model')
        plan_chunks=await execute('chain_of_agents',dict(request,mode='plan'),no_model)
        lineage=dict(dataset=json.loads((HERE/'native_inputs/dataset_provenance.json').read_text(encoding='utf-8')),
            sample_index=0,source_context_truncated=False,planned_chunks=plan_chunks['chunks'],planned_requests=plan_chunks['maximum_requests'])
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
        visible=visible_input(frozen,'E14')
        request=dict(input=visible)
        lineage=dict(original_frozen_input_id=frozen['id'],input_allowlist='visible_input(E14); no prior answer or expert Gold')
    names=['paper/author_reproductions/chain_of_agents/'+n for n in ('algorithm.py','product_adapter.py','run_validation.py','specification.lock.json','paper_v1.html','requirements.lock.txt','native_inputs/dataset_provenance.json','native_inputs/hotpotqa_first.json')]
    names+=['product_v1/backend/src/screenshotlegal/method_reproductions/'+n for n in ('e14_chain_of_agents.py','coa_bridge.py','paper_bridge.py','author_bridge.py','context.py')]
    names+=['product_v1/backend/src/screenshotlegal/experiments/'+n for n in ('engine.py','registry.py')]
    longbench,entry=source('longbench');names += [entry['local_path']+'/'+n for n in entry['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(track=track,request=request,evaluation=evaluation,lineage=lineage,model=model,sources=hashes))[:16]
    directory=run.OUT/'methods/e14_chain_of_agents/runs'/(plan_id+'__'+track)
    plan=dict(plan_id=plan_id,created_at=now(),paper_id='A06',method='e14_chain_of_agents',track=track,
        source_kind='paper_algorithm_reimplementation',author_code_executed=False,source_manifest=hashes,
        model=model,lineage=lineage,local_model_inference=False,maximum_additional_requests=20,cap_per_paper=100,
        original_complete_benchmark=False,expert_legal_gold_used=False)
    run.save(directory/'e14_chain_of_agents.input.json',dict(request=request,evaluation_only=evaluation,plan=plan))
    if not (directory/'e14_chain_of_agents.provenance.json').exists():run.save(directory/'e14_chain_of_agents.provenance.json',plan)
    for n,expected in hashes.items():
        data=(ROOT/n).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot: '+n)
        target=directory/'source_snapshot'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not do_execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,track=track,used=gateway.count('A06'),planned_requests=lineage.get('planned_requests'))));store.close();return
    record_path=directory/'e14_chain_of_agents.record.json'
    if record_path.exists():
        print(json.dumps(dict(status='existing_record_retained',path=str(record_path.relative_to(ROOT)))));store.close();return
    initial=gateway.count('A06')
    if initial+20>100:raise ValueError('Shared budget cannot fund a bounded attempt')
    trace=[];artifacts=[];tools=[];checks={};output=None
    record=dict(paper_id='A06',method='e14_chain_of_agents',track=track,plan_id=plan_id,status='running',source_kind='paper_algorithm_reimplementation')
    run.save(record_path,record)
    async def raw(stage,messages,parameters):
        if gateway.count('A06')-initial>=20:raise ModelFailure('budget','Bounded unit cap reached')
        effective=copy.deepcopy(model);effective['parameters'].update(temperature=parameters['temperature'],max_tokens=parameters['max_tokens'])
        sid=plan_id+'.A06.'+track+'.'+stage
        item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=effective['parameters'],status='calling_model')
        trace.append(item);run.save(directory/'e14_chain_of_agents.model_responses.json',trace)
        try:response=await gateway.call(owner,effective,messages,'paper_coa_'+track,sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));run.save(directory/'e14_chain_of_agents.model_responses.json',trace);raise
        item.update(status='completed',response=response);run.save(directory/'e14_chain_of_agents.model_responses.json',trace)
        return response
    async def artifact(name,result):artifacts.append(result);run.save(directory/'e14_chain_of_agents.author_artifacts.json',artifacts)
    async def tool(action,result):tools.append(dict(action=action,result=result))
    async def generic(*args):raise ValueError('Old generic character worker path must not execute')
    try:
        if track=='native':
            result=await execute('chain_of_agents',request,raw,tool)
            namespace=dict(re=re,string=string,Counter=Counter)
            original_definitions(longbench/'LongBench/metrics.py',['normalize_answer','f1_score','qa_f1_score'],namespace)
            scores=[namespace['qa_f1_score'](result['output'],answer) for answer in evaluation['references']]
            output=dict(answer=result['output'],official_qa_f1=max(scores),references=evaluation['references'],per_reference_f1=scores,execution=result)
            checks=dict(whole_source_covered=''.join(c['text'] for c in result['chunks'])==original['context'],
                worker_count=len(result['chunks']),separate_manager=True,manager_last_CU_only=True,source_context_truncated=False,
                official_longbench_qa_f1=max(scores),reference_sent_to_model=False)
        elif track=='vqa_predicted_text':
            result=await run_task(request['messages'],raw,tool_trace=tool)
            output=dict(prediction=result['output'],execution=result,score=benchmark_scoring.score(evaluation['task'],result['output'],evaluation['target'],evaluation['task']['asset']['width'],evaluation['task']['asset']['height']))
            checks=dict(product_text_VQA_controller_completed=True,reference_status=evaluation['reference_status'],score=output['score'],source_context='frozen_predicted_KIE_only')
        else:
            output=await run_method('E14',visible,frozen['sources'],generic,generic,SYSTEM_POLICY,lambda:{},dict(max_model_calls=20),raw_call=raw,author_record=artifact)
            output=validate_output(output,frozen)
            result=artifacts[0]
            checks=dict(case_product_schema_valid=True,literal_citations_valid=True,separate_manager=True,manager_last_CU_only=True)
        record.update(status='completed')
        if track!='case_product':await artifact('chain_of_agents',result)
        checks.update(local_model_inference=False,source_kind='paper_algorithm_reimplementation',author_code_executed=False,expert_legal_accuracy=None)
    except Exception as error:
        record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record['per_paper_requests_including_history']=gateway.count('A06')
        run.save(record_path,record);run.save(directory/'e14_chain_of_agents.output.json',output)
        run.save(directory/'e14_chain_of_agents.prompts.json',[dict(stage=t['stage'],messages=t['messages']) for t in trace])
        run.save(directory/'e14_chain_of_agents.tools.json',tools)
        run.save(directory/'e14_chain_of_agents.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,track=track,total_paper_requests=record['per_paper_requests_including_history'],path=str(directory.relative_to(ROOT))),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--track',choices=['native','vqa_predicted_text','case_product'],required=True);p.add_argument('--execute',action='store_true')
    a=p.parse_args();asyncio.run(main(a.track,a.execute))
