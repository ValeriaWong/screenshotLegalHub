"""Resume an interrupted native RAPTOR plan using durable responses, never resending unknown calls.

Only algorithm-relevant source hashes may match; unrelated source changes are disclosed.
Run only after confirming the old process is absent. Same plan/request IDs retain the paper cap.
"""
import argparse,asyncio,copy,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'product_v1/backend/src')]
from paper.author_reproductions import run_per_paper_validation as runner
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.method_reproductions.paper_bridge import execute
from screenshotlegal.research.contracts import now,digest
from screenshotlegal.research.gateway import error_view
class ReplayBoundary(Exception):pass

async def main(args):
    out=runner.OUT;plan=json.loads((out/'plans'/args.plan/'per_paper_plan.json').read_text(encoding='utf-8'))
    paper=args.paper;name,adapter={'R03':('e15_raptor','raptor'),'L09':('e19_scale','scale')}[paper];directory=out/'methods'/name/'runs'/(args.plan+'__native')
    old=json.loads((directory/(name+'.record.json')).read_text(encoding='utf-8'))
    if old['status']=='completed' and not args.replay_only:raise ValueError('Completed plan needs no resume')
    if args.replay_only:
        directory=directory/'replay_validation';directory.mkdir(parents=True,exist_ok=True)
    expected=plan['input']['source_manifest'];verified={};unrelated=[]
    for relative,sha in expected.items():
        actual=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
        relevant=('/'+adapter+'/' in relative or relative.endswith(('author_runtime.py','local_models.lock.json','paper_bridge.py')))
        if relevant and actual!=sha:raise ValueError('Relevant algorithm source differs: '+relative)
        if relevant:verified[relative]=sha
        elif actual!=sha:unrelated.append(relative)
    runner.base.OUT=out;store,configuration,config,owner,_=runner.base.prepare()
    approved=json.loads((out/'authorization.json').read_text(encoding='utf-8'))
    prefs=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=runner.PaperGateway(store,SimpleNamespace(preferences=lambda _:prefs),configuration,owner,approved['limit_per_paper'],approved['historical_counts']);gateway.paper=paper
    requests=store.list('author.paper_request',owner);prior=next(r for r in requests if r['id'].startswith(args.plan+'.'+paper+'.native.'))
    model=prior['model'];start=gateway.count(paper);trace=[];tools=[]
    runner.save(directory/(name+'.interrupted_record.json'),old)
    native=json.loads((out/'plans'/args.plan/'native_inputs'/(paper+'.json')).read_text(encoding='utf-8'))
    runner.save(directory/(name+'.input.json'),native)
    runner.save(directory/(name+'.recovery_provenance.json'),dict(resumed_at=now(),old_process_confirmed_absent=args.old_process,verified_relevant_sources=verified,changed_unrelated_sources=unrelated,replay_policy='Completed same-input responses only; unknown/failed requests are never resent'))
    async def call(stage,messages,parameters):
        current=copy.deepcopy(model);cap=parameters.get('max_tokens')
        current['parameters']['max_tokens']=min(6144,cap if isinstance(cap,int) and cap>0 else 6144)
        if parameters.get('stop'):current['parameters']['stop']=parameters['stop']
        if isinstance(parameters.get('temperature'),(int,float)):current['parameters']['temperature']=parameters['temperature']
        sid=runner.native_request_id(args.plan,paper,stage);saved=store.optional('evaluation.request',sid,owner)
        if args.replay_only and not saved:raise ReplayBoundary('All preceding requests replayed; next uncached stage '+stage+' was not sent')
        row=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=current['parameters'],replayed=bool(saved),status='calling_model');trace.append(row)
        runner.save(directory/(name+'.model_responses.json'),trace)
        response=await gateway.call(owner,current,messages,'native_author_'+paper,sid)
        row.update(status='completed',response=response);runner.save(directory/(name+'.model_responses.json'),trace)
        print(json.dumps(dict(stage=stage,replayed=bool(saved),paper_used=gateway.count(paper))),flush=True)
        return response
    async def tool(action,result):tools.append(dict(action=action,result=result));runner.save(directory/(name+'.tools.json'),tools)
    try:
        result=await execute(adapter,native['input'],call,tool)
        record=dict(paper_id=paper,method=name,track='native',status='completed',plan_id=args.plan,result=result,per_paper_requests_including_history=gateway.count(paper),resumed=True)
        runner.save(directory/(name+'.output.json'),result)
        runner.save(directory/(name+'.prompts.json'),[dict(stage=r['stage'],messages=r['messages']) for r in trace])
        runner.save(directory/(name+'.test_results.json'),dict(status='completed',checks=(dict(author_controller_completed=True,summary_layers=len(result['tree']['layers'])-1,layer_node_counts=result['tree']['layers'],answer_quality='manual_review_required') if paper=='R03' else dict(author_controller_completed=True,articles_processed=list(result['output']),issue_factor_guide_paths_preserved=bool(result['paths']),product_adaptation_completed=False,answer_quality='expert_review_deferred')),original_complete_benchmark=False,new_supplier_requests_on_resume=gateway.count(paper)-start,replayed_responses=sum(r['replayed'] for r in trace)))
        runner.save(directory/(name+'.provenance.json'),dict(plan_id=args.plan,model=model,source_manifest=expected,native_input_hash=digest(native),limit_per_paper=approved['limit_per_paper']))
    except ReplayBoundary as boundary:
        record=dict(paper_id=paper,method=name,track='replay_only',status='completed',plan_id=args.plan,replayed_responses=len(trace),new_supplier_requests=gateway.count(paper)-start,next_stage_not_sent=str(boundary))
        runner.save(directory/(name+'.test_results.json'),dict(status='completed',new_supplier_requests=0,replayed_responses=len(trace),native_task_completed=False))
    except Exception as error:
        record=dict(paper_id=paper,method=name,track='native',status='failed',plan_id=args.plan,error=error_view(error),error_message=str(error),resumed=True,per_paper_requests_including_history=gateway.count(paper))
        runner.save(directory/(name+'.test_results.json'),dict(status='failed',error=error_view(error),original_complete_benchmark=False))
        raise
    finally:
        runner.save(directory/(name+'.record.json'),record);store.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--replay-only',action='store_true');p.add_argument('--paper',choices=['R03','L09'],default='R03');p.add_argument('--plan',required=True);p.add_argument('--old-process',required=True);asyncio.run(main(p.parse_args()))
