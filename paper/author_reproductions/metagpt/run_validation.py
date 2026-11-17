"""MetaGPT original task/product validation; shared A04 <=100 durable supplier requests."""
import argparse,ast,asyncio,copy,hashlib,json,sqlite3,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as base
from screenshotlegal.research.store import Store
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.research.gateway import ModelFailure,error_view
from screenshotlegal.method_reproductions.paper_bridge import execute
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.experiments.engine import visible_input,SYSTEM_POLICY,validate_output
from screenshotlegal.method_reproductions.context import MethodContext

async def main(args):
    config=base.base.ReadOnlyConfiguration(ROOT/'product_v1/data');model_config=config.get('model_configs',base.base.MODEL_ID);owner=model_config['owner_id']
    auth=json.loads((base.OUT/'authorization.json').read_text(encoding='utf-8'))
    if auth['limit_per_paper']!=100:raise PermissionError('Existing paper authorization cannot be reset')
    store=Store(base.OUT/'.runtime');preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),config,owner)
    gateway=base.PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),config,owner,100,auth['historical_counts']);gateway.paper='A04'
    model=gateway.freeze(owner,base.base.MODEL_ID)
    request=dict(mode='native',idea='Write a cli snake game')
    frozen=None;visible=None
    if args.track=='case_product':
        path=ROOT/'paper/experiments/results/2026-10-28-deepseek-pilot/.runtime/research/research.sqlite3'
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            frozen=json.loads(db.execute("SELECT body FROM records WHERE kind='agent.input' ORDER BY id LIMIT 1").fetchone()[0])
        visible=visible_input(frozen,'E22')
        law_sources=json.loads((ROOT/'paper/author_reproductions/scale/native_inputs/legal_sources.json').read_text(encoding='utf-8'))
        legal={a['id']:a for a in law_sources['authorities']}
        visible['legal_corpus']=[legal[a['id']] for a in frozen['legal_corpus']]
        request=dict(input=visible,instruction=MethodContext(visible,frozen['sources'],None,None,SYSTEM_POLICY,lambda:{},{}).final_system,independent_legal_provenance=law_sources['provenance'])
    names=['paper/author_reproductions/metagpt/'+p for p in ['loader.py','product_adapter.py','case_adapter.py','run_validation.py','requirements.lock.txt']]
    names+=['product_v1/backend/src/screenshotlegal/method_reproductions/e22_metagpt.py','product_v1/backend/src/screenshotlegal/method_reproductions/metagpt_bridge.py','paper/author_reproductions/scale/native_inputs/legal_sources.json','paper/author_reproductions/author_runtime.py','product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py']
    source=next(s for s in json.loads((ROOT/'paper/author_reproductions/sources.lock.json').read_text(encoding='utf-8')) if s['name']=='metagpt')
    names += [source['local_path']+'/'+name for name in source['files']]
    hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    plan_id=digest(dict(request=request,model=model,source=hashes))[:16]
    directory=base.OUT/'methods/e22_metagpt/runs'/(plan_id+'__'+args.track)
    if args.track=='native':request['runtime']=str(directory/'.runtime/author')
    plan=dict(plan_id=plan_id,created_at=now(),source_manifest=hashes,model=model,paper_id='A04',track=args.track,
              input_selection='author v0.3.0 README startup command: Write a cli snake game' if args.track=='native' else 'lexicographically first existing authorized frozen case; independent legal text enriched; no Gold or answer selection',maximum_additional_requests=40 if args.track=='native' else 4,
              limit_per_paper=100,original_complete_benchmark=False,local_model_inference=False)
    base.save(directory/'e22_metagpt.input.json',request);base.save(directory/'e22_metagpt.provenance.json',plan)
    for name,expected in hashes.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Code changed before snapshot')
        out=directory/'source_snapshot'/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
    if not args.execute:
        print(json.dumps(dict(status='planned',plan_id=plan_id,used=gateway.count('A04'),supplier_requests=0)));store.close();return
    record_path=directory/'e22_metagpt.record.json'
    if record_path.exists():print(json.dumps(dict(status='existing_record_retained',plan_id=plan_id)));store.close();return
    initial=gateway.count('A04')
    if initial>(60 if args.track=='native' else 96):raise ModelFailure('budget','Insufficient shared paper budget for bounded native software unit')
    record=dict(paper_id='A04',method='e22_metagpt',track=args.track,status='running',plan_id=plan_id)
    trace=[];tools=[];checks={};base.save(record_path,record)
    async def call(stage,messages,parameters):
        if gateway.count('A04')-initial>=(40 if args.track=='native' else 4):raise ModelFailure('budget','40-request native unit reached; no next request sent')
        sid=plan_id+'.A04.'+args.track+'.'+stage
        current=copy.deepcopy(model);current['parameters']['temperature']=0.
        item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=current['parameters'],status='calling_model')
        trace.append(item);base.save(directory/'e22_metagpt.model_responses.json',trace)
        try:response=await gateway.call(owner,current,messages,'author_metagpt_'+args.track,sid)
        except Exception as error:
            item.update(status='failed',error=error_view(error));base.save(directory/'e22_metagpt.model_responses.json',trace);raise
        item.update(status='completed',response=response);base.save(directory/'e22_metagpt.model_responses.json',trace)
        return response
    async def tool(action,result):
        tools.append(dict(action=action,result=result));base.save(directory/'e22_metagpt.tools.json',tools)
    try:
        if args.track=='case_product':
            artifacts=[]
            async def artifact(name,value):
                artifacts.append(value);base.save(directory/'e22_metagpt.author_artifacts.json',artifacts)
            async def generic(*args):raise ValueError('Product must dispatch author framework, not generic stages')
            output=await run_method('E22',visible,frozen['sources'],generic,generic,SYSTEM_POLICY,lambda:{},{},raw_call=call,author_record=artifact)
            output=validate_output(output,frozen)
            result=artifacts[0]
            record.update(status='completed',result=result)
            checks=dict(author_controller_completed=True,product_case_output_schema_valid=True,literal_citations_valid=True,
                        subscriptions_preserved=len(result['subscriptions'])==4,structured_messages=len(result['messages']),
                        local_model_inference=False,expert_legal_accuracy=None)
            base.save(directory/'e22_metagpt.output.json',output);base.save(directory/'e22_metagpt.tools.json',result['tools'])
            return
        result=await execute('metagpt',request,call,tool)
        files=result['output']['files'];stages=[r['stage'].split('.')[0] for r in trace]
        python_files={p:s for p,s in files.items() if p.endswith('.py')}
        syntax={}
        for path,content in python_files.items():
            try:ast.parse(content,filename=path);syntax[path]=True
            except SyntaxError:syntax[path]=False
        checks=dict(author_controller_completed=True,all_software_stages_run=all(s in stages for s in ['WritePRD','WriteDesign','WriteTasks','WriteCode','WriteCodeReview']),
                    written_python_files=len(python_files),syntax=syntax,all_requests_completed=all(r['status']=='completed' for r in trace),
                    local_model_inference=False,functional_task_validation='pending generated-code review',original_benchmark_score=None)
        record.update(status='completed' if checks['all_software_stages_run'] and checks['all_requests_completed'] and python_files and all(syntax.values()) else 'failed',result=result)
        base.save(directory/'e22_metagpt.output.json',result)
    except Exception as error:
        record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
    finally:
        record['per_paper_requests_including_history']=gateway.count('A04')
        base.save(record_path,record)
        base.save(directory/'e22_metagpt.prompts.json',[dict(stage=r['stage'],messages=r['messages']) for r in trace])
        base.save(directory/'e22_metagpt.test_results.json',dict(status=record['status'],checks=checks,original_complete_benchmark=False))
        print(json.dumps(dict(status=record['status'],plan_id=plan_id,used=record['per_paper_requests_including_history'],path=str(directory.relative_to(ROOT)))))
        store.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--track',choices=['native','case_product'],default='native');p.add_argument('--execute',action='store_true')
    asyncio.run(main(p.parse_args()))
