"""LegalBench original task representatives and metric families; same durable <=100 paper cap.
Native I/O, source, innovation and fidelity are at top of product_adapter.py.
Original prompt generator and original evaluator functions; no local weights. All raw artifacts retained.
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
    source_root=ROOT/'paper/upstream_sources/legalbench'
    async def no_model(event):raise ValueError('Preparing original task inputs must not call a model')
    prepared=await stream_author(ROOT/'paper/.author_envs/legalbench/Scripts/python.exe',HERE/'product_adapter.py',dict(mode='prepare'),no_model,python_utf8=True)
    request=dict(mode='native',frozen_groups=prepared['groups'],template_checks=prepared['template_checks'])
    config=base.base.ReadOnlyConfiguration(ROOT/'product_v1/data');owner=config.get('model_configs',base.base.MODEL_ID)['owner_id']
    auth=json.loads((base.OUT/'authorization.json').read_text(encoding='utf-8'))
    if auth['limit_per_paper']!=100:raise PermissionError('Paper cap cannot reset')
    store=Store(base.OUT/'.runtime');preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),config,owner)
    gateway=base.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),config,owner,100,auth['historical_counts']);gateway.paper='B04'
    model=gateway.freeze(owner,base.base.MODEL_ID);unit_cap=60
    names=['paper/author_reproductions/legalbench/'+n for n in ['product_adapter.py','run_native.py','requirements.lock.txt']]
    names+=['product_v1/backend/src/screenshotlegal/method_reproductions/b04_legalbench.py','product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py','paper/author_reproductions/author_runtime.py']
    for pin in json.loads((HERE.parent/'sources.lock.json').read_text(encoding='utf-8')):
        if pin['name'] in ['legalbench','legalbench_data']:names += [pin['local_path']+'/'+n for n in pin['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(request=request,model=model,sources=hashes,unit_cap=unit_cap))[:16]
    directory=base.OUT/'methods/b04_legalbench/runs'/(plan_id+'__native')
    request['runtime']=str(directory/'.runtime/author')
    plan=dict(plan_id=plan_id,paper_id='B04',method='b04_legalbench',track='native',created_at=now(),source_manifest=hashes,model=model,
        maximum_additional_requests=unit_cap,limit_per_paper=100,original_notebook_llm_controller_not_supplied=True,api_transport_added=True,original_complete_benchmark=False,local_model_inference=False,python_utf8=True)
    base.save(directory/'b04_legalbench.input.json',request);base.save(directory/'b04_legalbench.provenance.json',plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot')
        target=directory/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not do_execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,used=gateway.count('B04'),additional_call_cap=unit_cap)));store.close();return
    record_path=directory/'b04_legalbench.record.json'
    if record_path.exists():print(json.dumps(dict(status='existing_record_retained',plan_id=plan_id)));store.close();return
    initial=gateway.count('B04')
    if initial+unit_cap>100:raise ModelFailure('budget','Insufficient shared B04 budget for bounded original examples')
    trace=[];tools=[];checks={};output=None
    record=dict(paper_id='B04',method='b04_legalbench',track='native',status='running',plan_id=plan_id)
    base.save(record_path,record)
    async def handle(event):
        if event['event']=='tool':
            tools.append(dict(action=event['action'],result=event['result']));base.save(directory/'b04_legalbench.tools.json',tools);return dict(ok=True)
        if gateway.count('B04')-initial>=unit_cap:raise ModelFailure('budget','LegalBench native unit cap reached; no next request')
        current=copy.deepcopy(model);current['parameters'].update(temperature=0,max_tokens=event['original_parameters']['model_max_tokens'])
        sid=plan_id+'.B04.native.'+event['stage']
        item=dict(stage=event['stage'],request_id=sid,messages=event['messages'],original_parameters=event['original_parameters'],effective_parameters=current['parameters'],status='calling_model')
        trace.append(item);base.save(directory/'b04_legalbench.model_responses.json',trace)
        try:response=await gateway.call(owner,current,event['messages'],'author_legalbench_native',sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));base.save(directory/'b04_legalbench.model_responses.json',trace);raise
        item.update(status='completed',response=response);base.save(directory/'b04_legalbench.model_responses.json',trace);return response
    try:
        output=await stream_author(ROOT/'paper/.author_envs/legalbench/Scripts/python.exe',HERE/'product_adapter.py',request,handle,python_utf8=True)
        checks=output['checks'];record.update(status='completed')
    except Exception as error:record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record.update(new_supplier_requests=gateway.count('B04')-initial,per_paper_requests_including_history=gateway.count('B04'))
        base.save(record_path,record);base.save(directory/'b04_legalbench.output.json',output);base.save(directory/'b04_legalbench.tools.json',tools)
        base.save(directory/'b04_legalbench.prompts.json',[dict(stage=r['stage'],messages=r['messages']) for r in trace])
        base.save(directory/'b04_legalbench.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,used=record['per_paper_requests_including_history'],new_supplier_requests=record['new_supplier_requests'],path=str(directory.relative_to(ROOT)))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args();asyncio.run(main(a.execute))
