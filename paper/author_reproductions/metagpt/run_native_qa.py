"""A04 original QaEngineer continuation, same durable <=100 paper budget.
Original source/method/I/O/scope are at the top of native_qa_adapter.py.
No full-startup claim: resumes previously author-generated, separately reviewed code.
All raw requests, subprocess outcomes, source snapshots and failed attempts retained.
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
    original=base.OUT/'methods/e22_metagpt/runs/46d2f9262b31af56__native'
    first=json.loads((original/'e22_metagpt.output.json').read_text(encoding='utf-8'))
    reviewed=json.loads((original/'e22_metagpt.native_followup_output.json').read_text(encoding='utf-8'))
    if not reviewed['manual_feedback_selection'] or not reviewed['functional_checks']['all_passed']:raise ValueError('Reviewed native seed provenance differs')
    design=next(m for m in first['output']['messages'] if m['cause_by']=='WriteDesign')
    request=dict(mode='native_qa_resume',files=reviewed['files'],design_message=design,rounds=8,
        seed_scope='previous real README snake project AFTER separately logged harness-selected original author review')
    config=base.base.ReadOnlyConfiguration(ROOT/'product_v1/data');owner=config.get('model_configs',base.base.MODEL_ID)['owner_id']
    auth=json.loads((base.OUT/'authorization.json').read_text(encoding='utf-8'))
    if auth['limit_per_paper']!=100:raise PermissionError('Paper cap cannot reset')
    store=Store(base.OUT/'.runtime');preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),config,owner)
    gateway=base.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),config,owner,100,auth['historical_counts']);gateway.paper='A04'
    model=gateway.freeze(owner,base.base.MODEL_ID);unit_cap=70
    names=['paper/author_reproductions/metagpt/'+n for n in ['loader.py','native_qa_adapter.py','run_native_qa.py','native_functional_probe.py','requirements.lock.txt']]
    names+=['product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py','paper/author_reproductions/author_runtime.py',
        str((original/'e22_metagpt.output.json').relative_to(ROOT)),str((original/'e22_metagpt.native_followup_output.json').relative_to(ROOT))]
    pin=next(s for s in json.loads((HERE.parent/'sources.lock.json').read_text(encoding='utf-8')) if s['name']=='metagpt')
    names+=[pin['local_path']+'/'+n for n in pin['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(request=request,model=model,sources=hashes,unit_cap=unit_cap))[:16]
    directory=base.OUT/'methods/e22_metagpt/runs'/(plan_id+'__native_qa')
    request['runtime']=str(directory/'.runtime/author')
    plan=dict(plan_id=plan_id,paper_id='A04',method='e22_metagpt',track='native_qa',created_at=now(),source_manifest=hashes,model=model,
        maximum_additional_requests=unit_cap,limit_per_paper=100,seed_after_harness_selected_review=True,fresh_full_startup=False,
        source_version_auto_development_repair_supported=False,original_complete_benchmark=False,local_model_inference=False,python_utf8=True)
    base.save(directory/'e22_metagpt.input.json',request);base.save(directory/'e22_metagpt.provenance.json',plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Source changed before snapshot')
        target=directory/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if not do_execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,used=gateway.count('A04'),additional_call_cap=unit_cap)));store.close();return
    record_path=directory/'e22_metagpt.record.json'
    if record_path.exists():print(json.dumps(dict(status='existing_record_retained',plan_id=plan_id)));store.close();return
    initial=gateway.count('A04')
    if initial+unit_cap>100:raise ModelFailure('budget','Insufficient shared A04 budget for bounded QA continuation')
    trace=[];tools=[];checks={};output=None
    record=dict(paper_id='A04',method='e22_metagpt',track='native_qa',status='running',plan_id=plan_id)
    base.save(record_path,record)
    async def handle(event):
        if event['event']=='tool':
            tools.append(dict(action=event['action'],result=event['result']));base.save(directory/'e22_metagpt.tools.json',tools);return dict(ok=True)
        if gateway.count('A04')-initial>=unit_cap:raise ModelFailure('budget','QA unit cap reached; no next request')
        current=copy.deepcopy(model);current['parameters'].update(temperature=0,max_tokens=event['original_parameters']['max_tokens'])
        sid=plan_id+'.A04.native_qa.'+event['stage']
        item=dict(stage=event['stage'],request_id=sid,messages=event['messages'],original_parameters=event['original_parameters'],effective_parameters=current['parameters'],status='calling_model')
        trace.append(item);base.save(directory/'e22_metagpt.model_responses.json',trace)
        try:response=await gateway.call(owner,current,event['messages'],'author_metagpt_native_qa',sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));base.save(directory/'e22_metagpt.model_responses.json',trace);raise
        item.update(status='completed',response=response);base.save(directory/'e22_metagpt.model_responses.json',trace);return response
    try:
        output=await stream_author(ROOT/'paper/.author_envs/metagpt/Scripts/python.exe',HERE/'native_qa_adapter.py',request,handle,python_utf8=True)
        checks=output['checks'];checks.update(local_model_inference=False,original_complete_benchmark=False,seed_after_harness_selected_review=True,
            qa_control_flow_completed=True,fresh_full_startup=False,legal_accuracy=None)
        record.update(status='completed')
    except Exception as error:record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record.update(new_supplier_requests=gateway.count('A04')-initial,per_paper_requests_including_history=gateway.count('A04'))
        base.save(record_path,record);base.save(directory/'e22_metagpt.output.json',output);base.save(directory/'e22_metagpt.tools.json',tools)
        base.save(directory/'e22_metagpt.prompts.json',[dict(stage=r['stage'],messages=r['messages']) for r in trace])
        base.save(directory/'e22_metagpt.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        store.close()
    print(json.dumps(dict(status=record['status'],plan_id=plan_id,used=record['per_paper_requests_including_history'],new_supplier_requests=record['new_supplier_requests'],path=str(directory.relative_to(ROOT)))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args();asyncio.run(main(a.execute))
