"""RAGChecker explicit invalid-reply recheck; same durable <=100 paper cap.
Native I/O, source, innovation and fidelity are at top of product_adapter.py.
Original extraction/checking and all 11 metrics; no local weights. All raw artifacts retained.
"""
import argparse,asyncio,copy,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as base
from screenshotlegal.research.store import Store
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.research.gateway import ModelFailure,error_view
from screenshotlegal.method_reproductions.author_bridge import stream_author

async def main(do_execute=False):
    previous=base.OUT/'methods/b15_ragchecker/runs/4848902c9cdff847__native'
    old_trace=json.loads((previous/'b15_ragchecker.model_responses.json').read_text(encoding='utf-8'))
    def prompt_key(messages,parameters):return digest(dict(messages=messages,original_parameters=parameters))
    cache={prompt_key(r['messages'],r['original_parameters']):r for r in old_trace}
    invalid=next(r for r in old_trace if r['stage']=='check.answer2response.17')
    invalid_key=prompt_key(invalid['messages'],invalid['original_parameters'])
    if invalid['response']['raw']!='carefully.\n\n### Answer:\n':raise ValueError('Original invalid reply provenance differs')
    source_root=ROOT/'paper/upstream_sources/ragchecker'
    request=dict(rag_results=json.loads((source_root/'examples/checking_inputs.json').read_text(encoding='utf-8')),metrics=['all_metrics'])
    config=base.base.ReadOnlyConfiguration(ROOT/'product_v1/data');owner=config.get('model_configs',base.base.MODEL_ID)['owner_id']
    auth=json.loads((base.OUT/'authorization.json').read_text(encoding='utf-8'))
    if auth['limit_per_paper']!=100:raise PermissionError('Paper cap cannot reset')
    store=Store(base.OUT/'.runtime');preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),config,owner)
    gateway=base.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),config,owner,100,auth['historical_counts']);gateway.paper='B15'
    model=gateway.freeze(owner,base.base.MODEL_ID);unit_cap=1
    names=['paper/author_reproductions/ragchecker/'+n for n in ['product_adapter.py','run_native_format_recheck.py','requirements.lock.txt']]
    names += [str((previous/'b15_ragchecker.model_responses.json').relative_to(ROOT))]
    names+=['product_v1/backend/src/screenshotlegal/method_reproductions/b15_ragchecker.py','product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py','paper/author_reproductions/author_runtime.py']
    for pin in json.loads((HERE.parent/'sources.lock.json').read_text(encoding='utf-8')):
        if pin['name'] in ['ragchecker','refchecker']:names += [pin['local_path']+'/'+n for n in pin['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(request=request,model=model,sources=hashes,unit_cap=unit_cap))[:16]
    directory=base.OUT/'methods/b15_ragchecker/runs'/(plan_id+'__native')
    request['runtime']=str(directory/'.runtime/author')
    plan=dict(plan_id=plan_id,paper_id='B15',method='b15_ragchecker',track='native',created_at=now(),source_manifest=hashes,model=model,recheck_of='4848902c9cdff847',reused_original_responses=True,unparsed_prompt_rechecked_once=True,one_checker_prompt_has_explicit_label_only_system_instruction=True,
        maximum_additional_requests=unit_cap,limit_per_paper=100,both_complete_public_examples=True,original_complete_benchmark=False,local_model_inference=False,python_utf8=True)
    base.save(directory/'b15_ragchecker.input.json',request);base.save(directory/'b15_ragchecker.provenance.json',plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot')
        target=directory/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not do_execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,used=gateway.count('B15'),additional_call_cap=unit_cap)));store.close();return
    record_path=directory/'b15_ragchecker.record.json'
    if record_path.exists():print(json.dumps(dict(status='existing_record_retained',plan_id=plan_id)));store.close();return
    initial=gateway.count('B15')
    if initial+unit_cap>100:raise ModelFailure('budget','Insufficient shared B15 budget for bounded original examples')
    trace=[];tools=[];checks={};output=None
    record=dict(paper_id='B15',method='b15_ragchecker',track='native',status='running',plan_id=plan_id)
    base.save(record_path,record)
    async def handle(event):
        if event['event']=='tool':
            tools.append(dict(action=event['action'],result=event['result']));base.save(directory/'b15_ragchecker.tools.json',tools);return dict(ok=True)
        key=prompt_key(event['messages'],event['original_parameters'])
        if key not in cache:raise ModelFailure('scope','Unseen prompt; exact response replay cannot continue')
        previous_item=cache[key]
        if key!=invalid_key:
            item=dict(stage=event['stage'],messages=event['messages'],original_parameters=event['original_parameters'],status='completed',supplier_request_new=False,reused_from_original_request_id=previous_item['request_id'],response=previous_item['response'])
            trace.append(item);base.save(directory/'b15_ragchecker.model_responses.json',trace);return previous_item['response']
        if gateway.count('B15')-initial>=unit_cap:raise ModelFailure('budget','Exactly one explicit invalid-reply recheck is allowed')
        current=copy.deepcopy(model);current['parameters'].update(temperature=0,max_tokens=event['original_parameters']['max_new_tokens'])
        forwarded=[dict(role='system',content='Return only one comma-separated sequence of Entailment, Neutral, or Contradiction, one label per claim in the original order. Do not include explanations, headings, repeated claims or reference text.')]+event['messages']
        sid=plan_id+'.B15.native.'+event['stage']
        item=dict(supplier_request_new=True,explicit_recheck_of=previous_item['request_id'],stage=event['stage'],request_id=sid,messages=forwarded,original_messages=event['messages'],original_parameters=event['original_parameters'],effective_parameters=current['parameters'],status='calling_model')
        trace.append(item);base.save(directory/'b15_ragchecker.model_responses.json',trace)
        try:response=await gateway.call(owner,current,forwarded,'author_ragchecker_native_format_adaptation',sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));base.save(directory/'b15_ragchecker.model_responses.json',trace);raise
        item.update(status='completed',response=response);base.save(directory/'b15_ragchecker.model_responses.json',trace);return response
    try:
        output=await stream_author(ROOT/'paper/.author_envs/ragchecker/Scripts/python.exe',HERE/'product_adapter.py',request,handle,python_utf8=True)
        checks=output['checks'];checks.update(original_responses_reused=sum(not r['supplier_request_new'] for r in trace),explicit_new_rechecks=sum(r['supplier_request_new'] for r in trace));record.update(status='completed',scope='45 exact original responses reused; one invalid checker reply rechecked with explicit output-format system instruction; original graph/metrics recomputed')
    except Exception as error:record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record.update(new_supplier_requests=gateway.count('B15')-initial,per_paper_requests_including_history=gateway.count('B15'))
        base.save(record_path,record);base.save(directory/'b15_ragchecker.output.json',output);base.save(directory/'b15_ragchecker.tools.json',tools)
        base.save(directory/'b15_ragchecker.prompts.json',[dict(stage=r['stage'],messages=r['messages']) for r in trace])
        base.save(directory/'b15_ragchecker.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,used=record['per_paper_requests_including_history'],new_supplier_requests=record['new_supplier_requests'],path=str(directory.relative_to(ROOT)))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args();asyncio.run(main(a.execute))
