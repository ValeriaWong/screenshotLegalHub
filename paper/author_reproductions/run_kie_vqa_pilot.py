"""Plan/execute a bounded author-native + product KIE/global-VQA development pilot.

Default command is read-only toward production and never calls a model. Execute
requires an explicit newly approved call cap and approval text. All versions share
one fixed durable request ledger, including failed/unknown requests. Raw records
are grouped by reproduction name; no expert legal accuracy is computed.
"""
import argparse
import asyncio
from contextlib import closing
import copy
from http.server import BaseHTTPRequestHandler,HTTPServer
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
from types import SimpleNamespace

REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'product_v1/backend/src'),str(REPO)]
from screenshotlegal.settings import Settings
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.research.store import Store
from screenshotlegal.research.gateway import Gateway,ModelFailure,request_messages,error_view
from screenshotlegal.research.benchmark import Benchmark,DEFAULTS
from screenshotlegal.research.benchmark_import import blob
from screenshotlegal.research.benchmark_pipeline import associate
from screenshotlegal.research.contracts import digest,now
from screenshotlegal.research.renderer import verified,atomic_write
from screenshotlegal.research.worker import Worker
from screenshotlegal.research.operations import public
from screenshotlegal.method_reproductions.author_bridge import source_manifest
from screenshotlegal.experiments.registry import CandidateRegistry
from screenshotlegal.method_reproductions.react_bridge import react
from paper.author_reproductions.self_refine.run import ReadOnlyConfiguration,MODEL_ID

OUT=REPO/'paper/author_reproductions/results/2026-10-28-kie-global-vqa'
NAMES={'E00':'e00_single_shot','E01':'e01_react','E05':'e05_self_refine'}

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(public(value),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def prepare():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'.gitignore').write_text('.runtime/\n',encoding='utf-8')
    configuration=ReadOnlyConfiguration(REPO/'product_v1/data')
    config=configuration.get('model_configs',MODEL_ID);owner=config['owner_id']
    source_root=REPO/'product_v1/data/research'
    with closing(sqlite3.connect((source_root/'research.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        record=db.execute('SELECT body FROM records WHERE kind=? AND owner=?',('benchmark.dataset',owner)).fetchone()
    if not record:raise ValueError('模型用户没有可用KIE/VQA数据集')
    source=json.loads(record[0]);tasks=json.loads(verified(source_root,source['tasks']).read_text(encoding='utf-8'))
    by_image={}
    for task in tasks:
        if task.get('migration_record_type')!='review_note' and task['asset_status']=='source_image_present':by_image.setdefault(task['image_name'],[]).append(task)
    for image_name,rows in sorted(by_image.items()):
        kie=next((t for t in rows if t['task_family']=='kie.extract'),None)
        global_tasks=sorted([t for t in rows if t['task_family']!='kie.extract' and not t.get('region_id') and t['answer_kind']=='categorical' and t.get('allowed_values')],key=lambda t:(t.get('source_label',''),t['task_id']))
        if kie and global_tasks:break
    else:raise ValueError('没有同时包含KIE和闭集全局VQA的原图样本')
    store=Store(OUT/'.runtime')
    asset=copy.deepcopy(kie['asset']);raw=verified(source_root,asset).read_bytes()
    extension={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}[asset['mime_type']]
    asset['path']='originals/'+asset['sha256']+extension
    atomic_write(store.root/asset['path'],raw)
    rows=copy.deepcopy(rows)
    for t in rows:t['asset']=asset
    local=copy.deepcopy(source);local.update(images={image_name:asset},counts=dict(images=1,kie=1,vqa=len(rows)-1,human_reviewed=0),tasks=blob(store,json.dumps(rows,ensure_ascii=False).encode()),image_files={image_name:blob(store,json.dumps(rows,ensure_ascii=False).encode())},replay=blob(store,b'{"details":[]}'))
    with store.tx() as db:
        existing=store.optional('benchmark.dataset',local['id'],owner,db)
        if existing and existing!=local:raise ValueError('隔离数据快照已变化，不覆盖已有任务')
        if not existing:store.put('benchmark.dataset',local,owner,db,immutable=True)
    implementation={p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in ['product_v1/backend/src/screenshotlegal/research/benchmark.py','product_v1/backend/src/screenshotlegal/research/benchmark_methods.py','product_v1/backend/src/screenshotlegal/research/gateway.py','product_v1/backend/src/screenshotlegal/research/worker.py']}
    implementation['agent_method_digest']=CandidateRegistry().code_digest
    from urllib.parse import urlsplit
    inference=dict(config_id=MODEL_ID,model=config['model_name'],endpoint_host=urlsplit(config['base_url']).hostname,enable_thinking=False,generation_max_output_tokens=6144,feedback_max_output_tokens=1024,native_acronym_max_output_tokens=300,product_temperature=0,native_acronym_temperature=.7)
    version=digest(dict(inference=inference,implementation=implementation,source_manifest=source_manifest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),image_sha256=asset['sha256'],tasks=[kie['task_id'],global_tasks[0]['task_id']]))[:16]
    plan=dict(plan_id=version,created_at=now(),selection='lexicographically first verified source image with KIE and closed-set global VQA; no output/answer selection',dataset_id=local['id'],image_name=image_name,image_sha256=asset['sha256'],kie_task_id=kie['task_id'],vqa_task_id=global_tasks[0]['task_id'],vqa_reference_status='legacy_unverified',kie_reference='no message transcript targets; schema/coordinates and legacy-region association only',source_manifest=source_manifest(),implementation=implementation,inference=inference,maximum_calls=56,units=[dict(method='E00',track='kie_image',maximum_calls=1),dict(method='E00',track='vqa_image_full',maximum_calls=1),dict(method='E05',track='native_acronym',maximum_calls=4),dict(method='E05',track='kie_image',maximum_calls=4),dict(method='E05',track='vqa_image_full',maximum_calls=4),dict(method='E01',track='native_hotpotqa',maximum_calls=14),dict(method='E01',track='kie_image',maximum_calls=14),dict(method='E01',track='vqa_image_full',maximum_calls=14)],original_benchmark_reproduced=False,legal_expert_evaluation_deferred=True)
    plan_path=OUT/'plans'/version/'plan.json'
    if plan_path.exists():plan=json.loads(plan_path.read_text(encoding='utf-8'))
    else:
        save(plan_path,plan)
        files=[name for name in source_manifest() if (REPO/name).is_file()]+[name for name in implementation if (REPO/name).is_file()]+[str(Path(__file__).relative_to(REPO)).replace(chr(92),'/')]
        files += [str(p.relative_to(REPO)).replace(chr(92),'/') for p in (REPO/'product_v1/backend/src/screenshotlegal/method_reproductions').glob('*.py')]
        for name in sorted(set(files)):
            destination=plan_path.parent/'implementation'/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes((REPO/name).read_bytes())
    save(OUT/'current_plan.json',plan)
    return store,configuration,config,owner,plan

class BoundedGateway(Gateway):
    def __init__(self,store,workspace,configuration,owner,limit):
        super().__init__(store,workspace);self.configuration,self.owner,self.limit=configuration,owner,limit
    def freeze(self,*args,**kwargs):
        model=super().freeze(*args,**kwargs)
        from urllib.parse import urlsplit
        if urlsplit(model['endpoint']).hostname not in ['aiping.cn','www.aiping.cn']:raise ValueError('本次思考开关只适配已核对的AI Ping端点')
        model['parameters'].update(enable_thinking=False,max_tokens=6144)
        return model
    async def call(self,owner,model,messages,purpose,request_id):
        old=self.store.optional('evaluation.request',request_id,owner)
        if old:
            if old['input_hash']!=digest(messages):raise ValueError('已存在请求的输入摘要不同，不复用也不重发')
            if old['status']=='completed':
                if not all(isinstance((old['response'].get('usage') or {}).get(k),int) for k in ['prompt_tokens','completion_tokens']):raise ModelFailure('usage_missing','既有响应缺少用量，不继续调用')
                return old['response']
            raise ModelFailure('previous_call_unresolved','既有失败/未知调用不自动重发',False,old['status'] in ['calling_model','unknown'])
        if len(self.store.list('evaluation.request',owner))>=self.limit:raise ModelFailure('budget','新增授权调用上限已用完')
        if not self.configuration.get('auth_users',owner).get('enabled') or not self.configuration.get('model_configs',MODEL_ID)['allow_external_egress']:raise PermissionError('模型或用户授权已撤销')
        response=await super().call(owner,model,messages,purpose,request_id)
        if not all(isinstance((response.get('usage') or {}).get(k),int) for k in ['prompt_tokens','completion_tokens']):raise ModelFailure('usage_missing','供应商用量缺失，原响应已保存；停止后续调用')
        return response

async def native_acronym(gateway,owner,model,directory,plan_id):
    token=secrets.token_urlsafe(32);trace=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.path!='/v1/chat/completions' or self.headers.get('Authorization')!='Bearer '+token:
                self.send_error(403);return
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            stage=['init','feedback.0','revise.1','feedback.1'][len(trace)]
            guidance=('Continue only the final title. Return exactly Acronym: <one acronym>.' if stage=='init' else 'Evaluate only the final title/acronym. Return Scores: with a short rubric and Total score: <integer>/25.' if stage.startswith('feedback.') else 'Revise only the final title/acronym using its feedback. Return Title: <new title> and Acronym: <new acronym>.')
            messages=copy.deepcopy(payload['messages']);messages[0]['content']+=' '+guidance+' Do not repeat examples; no hidden reasoning.'
            current=copy.deepcopy(model);current['parameters'].update(max_tokens=payload.get('max_tokens',300),temperature=payload.get('temperature',.7))
            if payload.get('stop'):current['parameters']['stop']=payload['stop']
            sid=plan_id+'.e05.native.'+stage
            entry=dict(stage=stage,request_id=sid,native_request=payload,effective_messages=messages,status='calling_model')
            trace.append(entry);save(directory/'e05_self_refine.native_trace.json',trace)
            try:
                response=asyncio.run(gateway.call(owner,current,messages,'author_native_self_refine',sid))
                entry.update(status='completed',response=response)
                save(directory/'e05_self_refine.native_trace.json',trace)
                body=json.dumps(dict(id=sid,object='chat.completion',model=payload['model'],usage=response.get('usage'),choices=[dict(index=0,finish_reason=response.get('finish_reason'),message=dict(role='assistant',content=response['raw']))])).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            except Exception as error:
                entry.update(status='failed',error=error_view(error));save(directory/'e05_self_refine.native_trace.json',trace)
                self.send_error(400,'Native model request failed; no automatic retry')
    server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    env={k:v for k,v in os.environ.items() if k not in ['OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','OPENAI_ORG']}
    env.update(AUTHOR_REPRO_BROKER_URL='http://127.0.0.1:'+str(server.server_port)+'/v1',AUTHOR_REPRO_BROKER_TOKEN=token,PYTHONIOENCODING='utf-8')
    try:
        python=REPO/'paper/.author_reproduction_env/Scripts/python.exe'
        process=await asyncio.create_subprocess_exec(str(python),'-B',str(REPO/'paper/author_reproductions/self_refine/driver.py'),'--out',str(directory),'--execute',env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr=await process.communicate()
        (directory/'e05_self_refine.stdout.log').write_bytes(stdout);(directory/'e05_self_refine.stderr.log').write_bytes(stderr)
        return dict(status='completed' if process.returncode==0 else 'failed',exit_code=process.returncode,controller='src.acronym.run.iterative_acronym',original_benchmark_reproduced=False,trace=trace)
    finally:server.shutdown();server.server_close()

async def execute(args):
    store,configuration,config,owner,plan=prepare()
    if args.command=='plan':
        print(json.dumps(dict(status='planned_only',plan_id=plan['plan_id'],maximum_calls=plan['maximum_calls'],new_model_requests=0),ensure_ascii=False));store.close();return
    if args.approved_additional_calls<=0 or not args.approval_text:raise PermissionError('需要本轮明确新增的调用额度和授权原文')
    authorization=OUT/'authorization.json'
    if authorization.exists():
        approved=json.loads(authorization.read_text(encoding='utf-8'))
        if approved['maximum_additional_calls']!=args.approved_additional_calls:raise PermissionError('已有授权额度不同，不重置持久调用账本')
    else:save(authorization,dict(maximum_additional_calls=args.approved_additional_calls,approval_text=args.approval_text,previous_known_method_requests=49,approved_at=now(),fixed_ledger=str(store.path.relative_to(OUT))))
    preferences=Preferences(Settings(data_dir=REPO/'product_v1/data'),configuration,owner)
    gateway=BoundedGateway(store,SimpleNamespace(preferences=lambda _:preferences),configuration,owner,args.approved_additional_calls)
    b=Benchmark(store,gateway);worker=Worker(store,None,gateway,None);worker.benchmark=b
    model=gateway.freeze(owner,MODEL_ID);results=[]
    try:
        for unit in plan['units']:
            name=NAMES[unit['method']];track=unit['track'];directory=OUT/'methods'/name/'runs'/(plan['plan_id']+'__'+track);directory.mkdir(parents=True,exist_ok=True)
            summary_path=directory/(name+'.record.json')
            if summary_path.exists():results.append(json.loads(summary_path.read_text(encoding='utf-8')));continue
            prior=store.list('evaluation.request',owner)
            halt=any(r['status']=='unknown' or (r.get('error') or {}).get('category')=='auth' or r['status']=='completed' and not all(isinstance(((r.get('response') or {}).get('usage') or {}).get(k),int) for k in ['prompt_tokens','completion_tokens']) for r in prior)
            image_unsupported=track in ['kie_image','vqa_image_full'] and any((r.get('error') or {}).get('category')=='input_unsupported' and r.get('purpose') in ['benchmark','benchmark_author_method'] for r in prior)
            if halt or image_unsupported:
                results.append(dict(method=name,track=track,status='not_started_service_prerequisite',reason='既有请求状态/用量未知或鉴权失败' if halt else '原图请求已被供应商明确拒绝，不继续重复送图'));continue
            remaining=args.approved_additional_calls-len(store.list('evaluation.request',owner))
            if remaining<unit['maximum_calls']:
                results.append(dict(method=name,track=track,status='not_started_budget',remaining_calls=remaining,required_ceiling=unit['maximum_calls']));continue
            print(name,track,flush=True)
            if track=='native_acronym':record=await native_acronym(gateway,owner,model,directory,plan['plan_id'])
            elif track=='native_hotpotqa':
                traces=[]
                async def call(stage,messages,parameters):
                    response=await gateway.call(owner,model,messages,'author_native_react',plan['plan_id']+'.e01.native.'+stage)
                    traces.append(dict(stage=stage,messages=messages,original_parameters=parameters,effective_parameters=model['parameters'],response=response));save(directory/(name+'.native_trace.json'),traces)
                    return response
                try:record=dict(status='completed',result=await react([dict(role='system',content='按原HotpotQA任务与原工具协议回答；只输出一句公开行动标签及Action，不输出隐含推理。'),dict(role='user',content='Use original dev question index 0')],call,native=True,native_index=0))
                except Exception as error:record=dict(status='failed',error_type=type(error).__name__,message=str(error))
            else:
                family='kie' if track=='kie_image' else 'vqa'
                prompt=b.save_prompt(owner,dict(name='author-pilot-'+family,family=family,parent_id=None,markdown=DEFAULTS[family],note='冻结KIE/全图VQA开发试跑',idempotency_key='author-pilot.prompt.'+family))
                p=dict(dataset_id=plan['dataset_id'],name=name+'.'+track,task_ids=[plan['kie_task_id'] if family=='kie' else plan['vqa_task_id']],track=track,mode='development_reference',model_id=MODEL_ID,prompt_id=prompt['id'],method_id=unit['method'],method_attempts=2,method_max_output_tokens=6144,max_calls=unit['maximum_calls'],iou_threshold=.6,idempotency_key=plan['plan_id']+'.'+name+'.'+track)
                run=b.create_run(owner,p)
                while job:=store.claim():await worker.execute(job)
                record=b.results(owner,run['id'])
                save(directory/(name+'.input.json'),[t['input'] for t in record['run']['tasks']]);save(directory/(name+'.model_responses.json'),record.get('method_steps') or record['attempts']);save(directory/(name+'.output.json'),[a.get('parsed') for a in record['attempts']])
                prompts=[dict(stage=s['stage'],messages=s['messages']) for s in record.get('method_steps',[])]
                if not prompts:
                    for t in record['run']['tasks']:
                        messages=request_messages(store,t['input']);messages[0]['content']=record['run']['prompt']['markdown'];prompts.append(dict(task_id=t['task_id'],messages=messages,source='rebuilt_from_frozen_input_and_prompt'))
                save(directory/(name+'.prompts.json'),prompts);save(directory/(name+'.tools.json'),record.get('method_tools',[]))
                if family=='kie':
                    task=record['run']['tasks'][0];attempt=next(iter(record['attempts']),{})
                    prediction=attempt.get('parsed');dataset=b.dataset(owner,plan['dataset_id']);rows=b.load(dataset['tasks'])
                    regions=sorted({tuple(t['bbox_xyxy']) for t in rows if t.get('bbox_xyxy')})
                    association=[]
                    if prediction:
                        for region in regions:association.append(dict(reference_bbox_xyxy=region,**associate(region,prediction['conversation'],task['asset']['width'],task['asset']['height'])))
                    save(directory/(name+'.kie_diagnostics.json'),dict(structure_valid=bool(prediction),predicted_messages=len(prediction['conversation']) if prediction else None,legacy_region_association=association,scope='unreviewed attribute-region association, not message detection F1 or transcription accuracy'))
            if track.startswith('native_'):
                native_trace=record.get('trace',traces if track=='native_hotpotqa' else [])
                save(directory/(name+'.model_responses.json'),native_trace)
                save(directory/(name+'.prompts.json'),[dict(stage=s.get('stage'),messages=s.get('effective_messages') or s.get('messages')) for s in native_trace])
                if track=='native_acronym':
                    for raw_file,suffix in [('native_plan.json','input'),('native_output.json','output')]:
                        raw_path=directory/raw_file
                        save(directory/(name+'.'+suffix+'.json'),json.loads(raw_path.read_text(encoding='utf-8')) if raw_path.exists() else None)
                else:
                    save(directory/(name+'.input.json'),dict(dataset='original HotpotQA dev',index=0,source_commit='6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9'))
                    save(directory/(name+'.output.json'),record.get('result',{}).get('output'))
            save(directory/(name+'.test_results.json'),dict(kind='native_single_task_contract_check' if track.startswith('native_') else 'development_reference',status=record.get('status') or record.get('run',{}).get('status'),scores=record.get('scores',[]),original_benchmark_reproduced=False,expert_legal_accuracy=None))
            save(directory/(name+'.provenance.json'),dict(plan_id=plan['plan_id'],source_manifest=plan['source_manifest'],implementation=plan['implementation'],original_benchmark_reproduced=False))
            record=dict(method=name,track=track,**record);save(summary_path,record);results.append(record)
        requests=store.list('evaluation.request',owner)
        costs=[(r.get('response') or (r.get('error') or {}).get('evidence') or {}).get('cost_estimate') for r in requests]
        save(OUT/'pilot_summary.json',dict(plan_id=plan['plan_id'],maximum_additional_calls=args.approved_additional_calls,new_requests=len(requests),estimated_cost_CNY=sum(costs) if all(c is not None for c in costs) else None,recorded_cost_CNY=sum(c for c in costs if c is not None),cost_missing_requests=sum(c is None for c in costs),units=results,original_benchmark_reproduced=False,legal_expert_evaluation_deferred=True))
        print(json.dumps(dict(new_requests=len(requests),unit_records=len(results)),ensure_ascii=False))
    finally:store.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['plan','execute'],nargs='?',default='plan');parser.add_argument('--approved-additional-calls',type=int,default=0);parser.add_argument('--approval-text',default='')
    asyncio.run(execute(parser.parse_args()))
