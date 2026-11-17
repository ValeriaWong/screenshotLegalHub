"""Execute the actual E19 product module with the shared durable L09 <=100 request ledger.
No local model weights. Inputs are allowlisted from a previously authorized frozen case.
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
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as run
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.store import Store
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.research.gateway import ModelFailure,error_view
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.method_reproductions.context import MethodContext
from screenshotlegal.experiments.engine import visible_input,SYSTEM_POLICY,validate_output

async def main(execute=False):
    configuration=run.base.ReadOnlyConfiguration(ROOT/'product_v1/data')
    config=configuration.get('model_configs',run.base.MODEL_ID);owner=config['owner_id']
    auth=json.loads((run.OUT/'authorization.json').read_text(encoding='utf-8'))
    if auth['limit_per_paper']!=100:raise ValueError('Existing per-paper authorization must be preserved')
    store=Store(run.OUT/'.runtime')
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=run.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,100,auth['historical_counts'])
    gateway.paper='L09'
    model=gateway.freeze(owner,run.base.MODEL_ID)
    path=ROOT/'paper/experiments/results/2026-10-28-deepseek-pilot/.runtime/research/research.sqlite3'
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        frozen=json.loads(db.execute("SELECT body FROM records WHERE kind='agent.input' ORDER BY id LIMIT 1").fetchone()[0])
    visible=visible_input(frozen,'E19')
    independent=json.loads((Path(__file__).parent/'native_inputs/legal_sources.json').read_text(encoding='utf-8'))
    laws={a['id']:a for a in independent['authorities']}
    visible['legal_corpus']=[laws[a['id']] for a in frozen['legal_corpus']]

    # Only the case product's allowlist is sent; reviewer Gold, old outputs and case notes are excluded.
    contract=MethodContext(visible,frozen['sources'],None,None,SYSTEM_POLICY,lambda:{},{})
    names=['paper/author_reproductions/scale/native_inputs/legal_sources.json','paper/author_reproductions/scale/prepare_legal_sources.py','paper/author_reproductions/scale/case_adapter.py','paper/author_reproductions/scale/run_case_product.py',
           'paper/author_reproductions/author_runtime.py','paper/author_reproductions/scale/requirements.lock.txt',
           'product_v1/backend/src/screenshotlegal/method_reproductions/e19_scale.py',
           'product_v1/backend/src/screenshotlegal/method_reproductions/scale_bridge.py',
           'product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py',
           'product_v1/backend/src/screenshotlegal/experiments/engine.py']
    lock=json.loads((ROOT/'paper/author_reproductions/sources.lock.json').read_text(encoding='utf-8'))
    original=next(s for s in lock if s['name']=='scale')
    names += [original['local_path']+'/'+n for n in original['files']]
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    plan_id=digest(dict(visible=visible,model=model,sources=hashes))[:16]
    directory=run.OUT/'methods/e19_scale/runs'/(plan_id+'__case_product')
    plan=dict(plan_id=plan_id,created_at=now(),paper_id='L09',track='case_product',
              input_selection='lexicographically first existing authorized frozen case input; no answer selection',
              independent_legal_text_provenance=independent['provenance'],original_frozen_input_id=frozen['id'],law_effective_date=frozen['law_effective_date'],
              source_manifest=hashes,author_commit=original['commit'],model=model,
              cap_per_paper=100,maximum_additional_requests=20,local_model_inference=False,
              expert_legal_gold_used=False,original_complete_benchmark=False)
    run.save(directory/'e19_scale.input.json',dict(input=visible,instruction=contract.final_system,plan=plan))
    run.save(directory/'e19_scale.provenance.json',plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot')
        target=directory/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not execute:
        print(json.dumps(dict(plan_id=plan_id,status='planned',used=gateway.count('L09'),supplier_requests=0)));store.close();return
    record_path=directory/'e19_scale.record.json'
    if record_path.exists():
        print(json.dumps(dict(status='existing_record_retained',path=str(record_path.relative_to(ROOT)))));store.close();return
    initial=gateway.count('L09')
    if initial>92:raise ModelFailure('budget','Not enough shared paper budget for a bounded product attempt')
    trace=[];artifacts=[]
    record=dict(paper_id='L09',method='e19_scale',track='case_product',plan_id=plan_id,status='running')
    run.save(record_path,record)
    async def raw(stage,messages,parameters):
        if gateway.count('L09')-initial>=20:raise ModelFailure('budget','Bounded product unit stopped before next request')
        current=copy.deepcopy(model)
        current['parameters']['temperature']=parameters.get('temperature',0)
        sid=plan_id+'.L09.case_product.'+stage
        item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,
                  effective_parameters=current['parameters'],status='calling_model')
        trace.append(item);run.save(directory/'e19_scale.model_responses.json',trace)
        try:response=await gateway.call(owner,current,messages,'author_scale_case_product',sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));run.save(directory/'e19_scale.model_responses.json',trace);raise
        item.update(status='completed',response=response);run.save(directory/'e19_scale.model_responses.json',trace)
        return response
    async def artifact(name,result):
        artifacts.append(dict(method=name,execution=result,sha256=digest(result)))
        run.save(directory/'e19_scale.author_artifacts.json',artifacts)
    async def disallow(*args):raise ValueError('SCALE must use original author stages, not baseline staged generation')
    try:
        result=await run_method('E19',visible,frozen['sources'],disallow,disallow,SYSTEM_POLICY,lambda:{},{},raw_call=raw,author_record=artifact)
        output=validate_output(result,frozen)
        record.update(status='completed',result=artifacts[0]['execution'])
        run.save(directory/'e19_scale.output.json',output)
        checks=dict(author_controller_completed=True,product_case_output_schema_valid=True,literal_citations_valid=True,
            guide_reference_path_preserved=bool(artifacts[0]['execution']['paths']['guide_paragraph_ids']),
            independent_guide_source_only=all(visible['sources'][0]['text'] not in json.dumps(x['messages'],ensure_ascii=False) for x in trace if x['stage'].startswith('guide_')),
            local_model_inference=False,expert_legal_accuracy=None)
    except Exception as error:
        record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error));checks={}
    finally:
        record['per_paper_requests_including_history']=gateway.count('L09')
        run.save(record_path,record)
        run.save(directory/'e19_scale.prompts.json',[dict(stage=r['stage'],messages=r['messages']) for r in trace])
        run.save(directory/'e19_scale.tools.json',artifacts[0]['execution']['paths'] if artifacts else [])
        run.save(directory/'e19_scale.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,total_paper_requests=record['per_paper_requests_including_history'],path=str(directory.relative_to(ROOT))),ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true')
    asyncio.run(main(parser.parse_args().execute))
