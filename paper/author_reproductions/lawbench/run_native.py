"""Native LawBench API validation. Per-paper shared durable cap <=100; no retries.
Source, benchmark, original I/O and adaptation scope: adapter.py and README.md.
The 38 samples are index 0 of 19 eligible tasks, zero-shot then one-shot. Public
references are held only in evaluator input; the one-shot author example remains.
Task 2-1 local LTP scoring is deferred. This is not 20,000-example paper accuracy.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as run
from paper.author_reproductions.lawbench.adapter import native_inputs
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.store import Store
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.research.gateway import error_view
from screenshotlegal.research.lawbench_scoring import official

async def main(execute=False):
    configuration=run.base.ReadOnlyConfiguration(ROOT/'product_v1/data')
    config=configuration.get('model_configs',run.base.MODEL_ID);owner=config['owner_id']
    auth=json.loads((run.OUT/'authorization.json').read_text(encoding='utf-8'))
    if auth['limit_per_paper']!=100:raise ValueError('Existing authorization cap changed')
    store=Store(run.OUT/'.runtime')
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=run.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,100,auth['historical_counts'])
    gateway.paper='B02';model=gateway.freeze(owner,run.base.MODEL_ID)
    inputs=native_inputs()
    lock=json.loads((ROOT/'paper/author_reproductions/sources.lock.json').read_text(encoding='utf-8'))
    source=next(s for s in lock if s['name']=='lawbench')
    names=['paper/author_reproductions/lawbench/'+n for n in ('adapter.py','run_native.py','requirements.lock.txt')]
    names+=['product_v1/backend/src/screenshotlegal/research/lawbench_scoring.py','paper/author_reproductions/run_per_paper_validation.py']
    names += [source['local_path']+'/'+n for n in source['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(inputs=inputs,model=model,sources=hashes))[:16]
    directory=run.OUT/'methods/b02_lawbench/runs'/(plan_id+'__native')
    plan=dict(plan_id=plan_id,created_at=now(),paper_id='B02',track='native',method='b02_lawbench',
        model=model,source_manifest=hashes,author_commit=source['commit'],
        maximum_additional_requests=len(inputs['samples']),cap_per_paper=100,local_model_inference=False,
        selection='row index 0, every non-deferred task, zero_shot and one_shot; no outcome selection',
        original_complete_benchmark=False,expert_legal_gold_used=False)
    run.save(directory/'b02_lawbench.input.json',inputs)
    if not (directory/'b02_lawbench.provenance.json').exists():run.save(directory/'b02_lawbench.provenance.json',plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot')
        path=directory/'source_snapshot'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    if not execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,additional_requests=len(inputs['samples']),used=gateway.count('B02'))));store.close();return
    record_path=directory/'b02_lawbench.record.json'
    if record_path.exists():
        print(json.dumps(dict(status='existing_record_retained',path=str(record_path.relative_to(ROOT)))));store.close();return
    if gateway.count('B02')+len(inputs['samples'])>100:raise ValueError('Shared paper budget cannot fund planned samples')
    record=dict(paper_id='B02',method='b02_lawbench',track='native',plan_id=plan_id,status='running')
    run.save(record_path,record);trace=[];predictions={};evaluations={};checks={}
    try:
        for sample in inputs['samples']:
            stage=sample['regime']+'.'+sample['task']+'.'+str(sample['index'])
            sid=plan_id+'.B02.native.'+stage
            item=dict(stage=stage,request_id=sid,messages=sample['messages'],reference_sent_to_model=False,status='calling_model')
            trace.append(item);run.save(directory/'b02_lawbench.model_responses.json',trace)
            response=await gateway.call(owner,model,sample['messages'],'author_lawbench_native',sid)
            item.update(status='completed',response=response)
            row=dict(origin_prompt=sample['origin_prompt'],prediction=response['raw'],refr=sample['reference'])
            predictions.setdefault(sample['regime'],{}).setdefault(sample['task'],[]).append(row)
            run.save(directory/'b02_lawbench.model_responses.json',trace)
            run.save(directory/'b02_lawbench.output.json',dict(predictions=predictions,evaluations=evaluations))
        for regime,tasks in predictions.items():
            evaluations[regime]=await official(tasks)
            run.save(directory/'b02_lawbench.output.json',dict(predictions=predictions,evaluations=evaluations))
            (directory/('b02_lawbench.'+regime+'.official_scores.csv')).write_text(evaluations[regime]['official_cli']['csv'],encoding='utf-8')
        checks=dict(author_dataset_samples=len(trace),original_task_types=19,prompt_regimes=2,
            original_functions_and_cli_executed=True,references_sent_to_model=False,
            local_model_inference=False,expert_legal_accuracy=None,original_paper_accuracy=None,
            deferred_task_ids=['2-1'],whole_method_marked_complete=False)
        record.update(status='completed',scope='19 task types x 2 regimes x first published sample; task 2-1 deferred')
    except Exception as error:
        if trace and trace[-1]['status']=='calling_model':trace[-1].update(status='failed',error=error_view(error))
        record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record['per_paper_requests_including_history']=gateway.count('B02')
        run.save(record_path,record)
        run.save(directory/'b02_lawbench.output.json',dict(predictions=predictions,evaluations=evaluations))
        run.save(directory/'b02_lawbench.model_responses.json',trace)
        run.save(directory/'b02_lawbench.prompts.json',[dict(stage=r['stage'],messages=r['messages']) for r in trace])
        run.save(directory/'b02_lawbench.tools.json',dict(evaluator=evaluations,deferred=inputs['deferred']))
        run.save(directory/'b02_lawbench.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,total_paper_requests=record['per_paper_requests_including_history'],path=str(directory.relative_to(ROOT))),ensure_ascii=False))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true')
    asyncio.run(main(parser.parse_args().execute))
