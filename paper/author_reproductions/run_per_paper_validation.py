"""Run native author tasks and product KIE/global-VQA with AIPING DeepSeek.

Every paper has a durable 100-request cap, including failed/unknown requests and
conservatively attributable historical requests. The native and product tracks
share the same per-paper ledger. No implicit retry, no reset at a new plan version.
"""
import argparse
import asyncio
import copy
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_kie_vqa_pilot as base
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.settings import Settings
from screenshotlegal.research.gateway import Gateway,ModelFailure,error_view,request_messages
from screenshotlegal.research.benchmark import Benchmark,DEFAULTS
from screenshotlegal.research.worker import Worker
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.method_reproductions.paper_bridge import execute as author_execute
from screenshotlegal.method_reproductions.react_bridge import react
from screenshotlegal.experiments.registry import CandidateRegistry

OUT=ROOT/'paper/author_reproductions/results/2026-10-29-per-paper'
NAMES={'BASELINE':('E00','e00_single_shot'), 'A02':('E05','e05_self_refine'),
       'A01':('E01','e01_react'), 'A03':('E21','e21_reflexion'),
       'L05':('E04','solar'), 'L01':('E07','agentscourt'),
       'R03':('E15','e15_raptor'), 'R05':('E16','e16_lightrag'), 'L09':('E19','e19_scale')}
save=base.save


def native_request_id(plan_id,paper,stage):
    return plan_id+'.'+paper+'.native.'+stage


def historical_counts():
    counts={}
    path=ROOT/'paper/experiments/results/2026-10-28-deepseek-pilot/.runtime/research/research.sqlite3'
    if path.exists():
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            runs={r['id']:r for r in [json.loads(x[0]) for x in db.execute("SELECT body FROM records WHERE kind='agent.run'")]}
            requests=[json.loads(x[0]) for x in db.execute("SELECT body FROM records WHERE kind='evaluation.request'")]
        registry=CandidateRegistry();refs={m['id']:m['references'] for m in registry.methods}
        for request in requests:
            run=runs.get(request['id'].split(':',1)[0])
            if run:
                for paper in refs.get(run['method']['id'],[]):counts[paper]=counts.get(paper,0)+1
    path=ROOT/'paper/author_reproductions/self_refine/runs/2026-10-28-native-acronym/.runtime/research/research.sqlite3'
    if path.exists():
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            counts['A02']=counts.get('A02',0)+db.execute("SELECT COUNT(*) FROM records WHERE kind='evaluation.request'").fetchone()[0]
    return counts


class PaperGateway(Gateway):
    def __init__(self,store,workspace,configuration,owner,limit,historical):
        super().__init__(store,workspace)
        self.configuration,self.owner,self.limit,self.historical=configuration,owner,limit,historical
        self.paper=None
    def count(self,paper):
        return self.historical.get(paper,0)+sum(r['paper_id']==paper for r in self.store.list('author.paper_request',self.owner))
    def freeze(self,*args,**kwargs):
        result=super().freeze(*args,**kwargs)
        from urllib.parse import urlsplit
        if urlsplit(result['endpoint']).hostname not in ['aiping.cn','www.aiping.cn']:
            raise ValueError('Approved AIPING endpoint does not match')
        result['parameters'].update(enable_thinking=False,thinking=dict(type='disabled'),max_tokens=6144)
        return result
    async def call(self,owner,model,messages,purpose,request_id):
        if not self.paper:raise ValueError('A paper budget scope is required')
        old=self.store.optional('evaluation.request',request_id,owner)
        if old:
            if old['input_hash']!=digest(messages):raise ValueError('Existing request input differs; no resend')
            if old['status']=='completed':return old['response']
            raise ModelFailure('previous_call_unresolved','Previous failed/unknown request is retained without automatic resend',False,old['status'] in ['calling_model','unknown'])
        if not self.configuration.get('auth_users',owner).get('enabled') or not self.configuration.get('model_configs',base.MODEL_ID)['allow_external_egress']:
            raise PermissionError('Model/owner authorization revoked')
        row=dict(id=request_id,paper_id=self.paper,purpose=purpose,messages=messages,input_hash=digest(messages),
                 model=model,status='reserved',created_at=now())
        with self.store.tx() as db:
            prior=self.store.optional('author.paper_request',request_id,owner,db)
            if prior:raise ModelFailure('previous_call_unresolved','Reserved request is retained; no resend',False,True)
            used=self.historical.get(self.paper,0)+sum(r['paper_id']==self.paper for r in self.store.list('author.paper_request',owner,db))
            if used>=self.limit:raise ModelFailure('budget','Per-paper 100-request cap reached; next request not sent')
            self.store.put('author.paper_request',row,owner,db)
        print(json.dumps(dict(event='model_request',paper=self.paper,used=used+1,limit=self.limit,request_id=request_id)),flush=True)
        try:
            result=await super().call(owner,model,messages,purpose,request_id)
            if not all(isinstance((result.get('usage') or {}).get(k),int) for k in ['prompt_tokens','completion_tokens']):
                raise ModelFailure('usage_missing','Response saved but usage missing; stop further inference')
            return result
        finally:
            actual=self.store.optional('evaluation.request',request_id,owner)
            row.update(status=actual['status'] if actual else 'not_sent',request=actual,finished_at=now())
            with self.store.tx() as db:self.store.put('author.paper_request',row,owner,db)
            save(OUT/'paper_budgets.json',dict(limit_per_paper=self.limit,historical=self.historical,
                 used={p:self.count(p) for p in set(NAMES)|set(self.historical)|{r['paper_id'] for r in self.store.list('author.paper_request',self.owner)}},updated_at=now()))


def plan_units(papers,tracks):
    units=[]
    for paper in papers:
        if paper!='BASELINE' and 'native' in tracks:units.append(dict(paper=paper,track='native'))
        if 'product' in tracks or any(t in tracks for t in ['kie_image','vqa_image_full','vqa_predicted_text']):
            if paper in ['BASELINE','A02','A01','A03']:
                units += [dict(paper=paper,track=t) for t in ['kie_image','vqa_image_full']]
            elif paper in ['R03','R05']:units.append(dict(paper=paper,track='vqa_predicted_text'))
    return [u for u in units if u['track']=='native' or 'product' in tracks or u['track'] in tracks]


async def main(args):
    base.OUT=OUT
    store,configuration,config,owner,input_plan=base.prepare()
    selected=args.papers.split(',') if args.papers else list(NAMES)
    if not set(selected)<=set(NAMES):raise ValueError('Unknown paper in this runner')
    native_inputs={}
    for paper,name in [('A03','reflexion'),('L05','solar'),('L01','agentscourt'),('R03','raptor'),('R05','lightrag'),('L09','scale')]:
        path=Path(__file__).parent/'native_inputs'/(name+'.json')
        if path.exists():native_inputs[paper]=json.loads(path.read_text(encoding='utf-8'))
    units=plan_units(selected,args.tracks.split(','))
    code=digest(dict(source_manifest=base.source_manifest(),runner=Path(__file__).read_text(encoding='utf-8'),native_inputs=native_inputs,units=units,input_plan_id=input_plan['plan_id']))[:16]
    plan=dict(plan_id=code,created_at=now(),input_plan_id=input_plan['plan_id'],input=input_plan,units=units,
              limit_per_paper=args.per_paper_limit,native_input_hashes={p:digest(v) for p,v in native_inputs.items()},
              original_complete_benchmark=False,expert_legal_evaluation_deferred=True)
    plan_path=OUT/'plans'/code/'per_paper_plan.json'
    if plan_path.exists():plan=json.loads(plan_path.read_text(encoding='utf-8'))
    else:
        save(plan_path,plan)
        (plan_path.parent/'run_per_paper_validation.py').write_bytes(Path(__file__).read_bytes())
        for paper,value in native_inputs.items():save(plan_path.parent/'native_inputs'/(paper+'.json'),value)
        for relative,sha256 in plan['input']['source_manifest'].items():
            content=(ROOT/relative).read_bytes()
            if hashlib.sha256(content).hexdigest()!=sha256:raise ValueError('Source changed before snapshot: '+relative)
            target=plan_path.parent/'source_snapshot'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    save(OUT/'current_per_paper_plan.json',plan)
    if args.command=='plan':print(json.dumps(dict(plan_id=code,units=units,provider_requests=0)));store.close();return
    if not args.approval_text or not 1<=args.per_paper_limit<=100:raise PermissionError('Explicit per-paper authorization required; maximum 100')
    authorization=OUT/'authorization.json'
    if authorization.exists():
        approved=json.loads(authorization.read_text(encoding='utf-8'))
        if approved['limit_per_paper']!=args.per_paper_limit:raise PermissionError('Existing limit cannot be reset')
        historical=approved['historical_counts']
    else:
        historical=historical_counts()
        save(authorization,dict(limit_per_paper=args.per_paper_limit,approval_text=args.approval_text,approved_at=now(),
            historical_counts=historical,counting='Supplier requests including failures/unknowns; historical project prototypes conservatively attributed by their cited paper IDs'))
    preferences=Preferences(Settings(data_dir=ROOT/'product_v1/data'),configuration,owner)
    gateway=PaperGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,args.per_paper_limit,historical)
    benchmark=Benchmark(store,gateway);worker=Worker(store,None,gateway,None);worker.benchmark=benchmark
    model=gateway.freeze(owner,base.MODEL_ID);records=[]
    try:
        for unit in units:
            paper,track=unit['paper'],unit['track'];mid,name=NAMES[paper];gateway.paper=paper
            directory=OUT/'methods'/name/'runs'/(code+'__'+track);directory.mkdir(parents=True,exist_ok=True)
            record_path=directory/(name+'.record.json')
            if record_path.exists():records.append(json.loads(record_path.read_text(encoding='utf-8')));continue
            print(json.dumps(dict(event='unit_start',paper=paper,method=name,track=track)),flush=True)
            trace=[];tools=[];checks={};record=dict(paper_id=paper,method=name,track=track,status='running',plan_id=code)
            save(record_path,record)
            try:
                if track=='native':
                    async def call(stage,messages,parameters):
                        current=copy.deepcopy(model)
                        original_cap=parameters.get('max_tokens')
                        current['parameters']['max_tokens']=min(6144,original_cap if isinstance(original_cap,int) and original_cap>0 else 6144)
                        if parameters.get('stop'):current['parameters']['stop']=parameters['stop']
                        if isinstance(parameters.get('temperature'),(int,float)):current['parameters']['temperature']=parameters['temperature']
                        if paper=='A03' and stage.startswith('action.'):
                            current['parameters']['max_tokens']=1024
                        sid=native_request_id(code,paper,stage)
                        item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=current['parameters'],status='calling_model')
                        trace.append(item);save(directory/(name+'.model_responses.json'),trace)
                        try:response=await gateway.call(owner,current,messages,'native_author_'+paper,sid)
                        except Exception as error:
                            item.update(status='failed',error=error_view(error));save(directory/(name+'.model_responses.json'),trace);raise
                        item.update(status='completed',response=response);save(directory/(name+'.model_responses.json'),trace)
                        return response
                    async def tool(action,result):tools.append(dict(action=action,result=result));save(directory/(name+'.tools.json'),tools)
                    if paper=='A02':
                        native=await base.native_acronym(gateway,owner,model,directory,code)
                        trace=native['trace'];result=dict(execution=native,author_output=json.loads((directory/'native_output.json').read_text(encoding='utf-8')) if (directory/'native_output.json').exists() else None)
                        native_input=json.loads((directory/'native_plan.json').read_text(encoding='utf-8')) if (directory/'native_plan.json').exists() else None
                        checks=dict(author_controller_completed=native['status']=='completed')
                    elif paper=='A01':
                        native_input=dict(dataset='author HotpotQA dev',index=0,commit='6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9')
                        result=await react([dict(role='system',content='Use the original HotpotQA task; only concise public action labels and actions, no private reasoning.'),dict(role='user',content='Use original dev index 0')],call,native=True,native_index=0)
                        checks=dict(author_controller_completed=True,answer_exact_match=bool(result.get('reward')))
                    else:
                        native_input=native_inputs[paper]
                        result=await author_execute({'A03':'reflexion','L05':'solar','L01':'agentscourt','R03':'raptor','R05':'lightrag','L09':'scale'}[paper],native_input['input'],call,tool)
                        checks=dict(author_controller_completed=True)
                        if paper=='A03':checks['answer_exact_match']=bool(result['trials'][-1]['feedback'])
                        if paper=='L05':
                            expected=float(native_input['reference'].replace('$','').replace(',',''));actual=result['output']['answer']
                            checks.update(expected=expected,actual=actual,rounded_exact_match=round(actual)==expected,within_original_10_percent=abs(actual-expected)<=abs(expected)*.1)
                        if paper=='L01':checks.update(debate_turns=len(result['output']),full_legal_kb_pipeline_completed=False)
                        if paper=='L09':checks.update(articles_processed=list(result['output']),issue_factor_guide_paths_preserved=bool(result['paths']),product_adaptation_completed=False,answer_quality='expert_review_deferred')
                        if paper=='R03':checks.update(summary_layers=len(result['tree']['layers'])-1,answer_quality='manual_review_required')
                        if paper=='R05':checks.update(graph_nodes=len(result['graph']['nodes']),graph_edges=len(result['graph']['edges']),reference=native_input.get('reference'),answer_quality='manual_review_required')
                    record.update(status='completed',result=result)
                    save(directory/(name+'.input.json'),native_input);save(directory/(name+'.output.json'),result)
                    save(directory/(name+'.model_responses.json'),trace)
                    save(directory/(name+'.prompts.json'),[dict(stage=s.get('stage'),messages=s.get('effective_messages') or s.get('messages')) for s in trace])
                else:
                    upstream=None
                    if track=='vqa_predicted_text':
                        attempts=[a for a in store.list('benchmark.attempt',owner) if a.get('task_family')=='kie.extract' and a.get('status')=='completed' and a.get('parsed',{}).get('conversation')]
                        if not attempts:raise ValueError('No valid frozen KIE prediction yet; do not fabricate text input')
                        upstream=sorted(attempts,key=lambda a:a['created_at'])[0]['id']
                    family='kie' if track=='kie_image' else 'vqa'
                    prompt=benchmark.save_prompt(owner,dict(name='author-per-paper-'+family,family=family,parent_id=None,markdown=DEFAULTS[family],note='原任务与截图适配分别验证',idempotency_key='per-paper.prompt.'+family))
                    remaining=max(0,args.per_paper_limit-gateway.count(paper))
                    ceiling={'BASELINE':1,'A02':4,'A01':14,'A03':5}.get(paper,min(remaining,40))
                    if remaining<ceiling:raise ModelFailure('budget','Not enough per-paper budget to start the bounded unit')
                    payload=dict(dataset_id=input_plan['dataset_id'],name=name+'.'+track,task_ids=[input_plan['kie_task_id'] if family=='kie' else input_plan['vqa_task_id']],track=track,
                        mode='development_reference',model_id=base.MODEL_ID,prompt_id=prompt['id'],method_id=mid,method_attempts=2,
                        method_max_output_tokens=6144,max_calls=ceiling,iou_threshold=.6,upstream_attempt_id=upstream,idempotency_key=code+'.'+paper+'.'+track)
                    run=benchmark.create_run(owner,payload)
                    while job:=store.claim():await worker.execute(job)
                    result=benchmark.results(owner,run['id']);record.update(status=result['run']['status'],result=result)
                    save(directory/(name+'.input.json'),[t['input'] for t in result['run']['tasks']]);save(directory/(name+'.output.json'),[a.get('parsed') for a in result['attempts']])
                    save(directory/(name+'.model_responses.json'),result.get('method_steps') or result['attempts']);save(directory/(name+'.tools.json'),result.get('method_tools',[]))
                    prompts=[dict(stage=s['stage'],messages=s['messages']) for s in result.get('method_steps',[])]
                    if not prompts:
                        prompts=[dict(task_id=t['task_id'],messages=request_messages(store,t['input'])) for t in result['run']['tasks']]
                        for row in prompts:row['messages'][0]['content']=result['run']['prompt']['markdown']
                    save(directory/(name+'.prompts.json'),prompts)
                    checks=dict(valid_outputs=sum(bool(a.get('parsed')) for a in result['attempts']),scores=result.get('scores',[]),expert_legal_accuracy=None)
            except Exception as error:
                record.update(status='failed',error=error_view(error),error_type=type(error).__name__,error_message=str(error))
                save(directory/(name+'.model_responses.json'),trace)
                if track=='native' and paper in native_inputs:save(directory/(name+'.input.json'),native_inputs[paper])
            record['per_paper_requests_including_history']=gateway.count(paper)
            save(directory/(name+'.test_results.json'),dict(checks=checks,status=record['status'],original_complete_benchmark=False,scope='Native task/adapter execution; expert legal metrics deferred'))
            save(directory/(name+'.provenance.json'),dict(plan_id=code,model=model,source_manifest=plan['input']['source_manifest'],native_input_hash=plan['native_input_hashes'].get(paper),limit_per_paper=args.per_paper_limit))
            save(record_path,record);records.append(record)
            requests=store.list('author.paper_request',owner)
            save(OUT/'validation_summary.json',dict(plan_id=code,records=records,new_provider_requests=len(requests),per_paper={p:gateway.count(p) for p in set(NAMES)|set(historical)},limit_per_paper=args.per_paper_limit))
            print(json.dumps(dict(event='unit_finished',paper=paper,track=track,status=record['status'],used=gateway.count(paper))),flush=True)
    finally:store.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['plan','execute'],default='plan',nargs='?')
    p.add_argument('--papers',default='');p.add_argument('--tracks',default='native,product');p.add_argument('--per-paper-limit',type=int,default=100);p.add_argument('--approval-text',default='')
    asyncio.run(main(p.parse_args()))
