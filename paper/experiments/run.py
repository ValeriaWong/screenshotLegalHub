"""Paper experiment runner. Calls the product API, never a second method implementation.

Demo creates a private temporary application with synthetic cases and no model network.
plan/execute target the user's configured product server; credentials stay in env.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from contextlib import contextmanager

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'product_v1/backend/src'))
from screenshotlegal.experiments.contracts import ExperimentCreate
from screenshotlegal.research.contracts import digest
from report import summarize
from method_artifacts import read_record,save_record
from screenshotlegal.method_reproductions.catalog import METHOD_MODULES

DEFAULT_METHODS=['E00','E01','E02','E03','E05','E06','E07','E08','E09','E10','E11','E12','E14','E18','E19','E20']

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def checked(response):
    if response.status_code>=400:
        raise ValueError(str(response.status_code)+': '+str(response.json().get('detail','request failed')))
    return response.json()

@contextmanager
def demo_client():
    # Set isolation before importing the module-level default FastAPI app.
    with tempfile.TemporaryDirectory(prefix='screenshotlegal-paper-demo-') as folder:
        os.environ['DATA_DIR']=folder
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config(str(REPO/'product_v1/backend/alembic.ini')),'head')
        from fastapi.testclient import TestClient
        from screenshotlegal.settings import Settings
        from screenshotlegal.api.main import create_app,app as bootstrap_app
        app=create_app(Settings(data_dir=Path(folder)))
        try:
            with TestClient(app) as client:
                checked(client.post('/v1/auth/setup',json=dict(username='paper-demo',password='synthetic-demo-password-2026',display_name='Isolated paper demo')))
                yield client
        finally:
            for instance in [app,bootstrap_app]:
                instance.state.research['store'].close()
                instance.state.workspace.repo.engine.dispose()

def demo_manifest(client):
    fixtures=[
        ('simple','甲：收到520元。乙：下周归还。'),
        ('counterevidence','甲：款项是借款。乙：我认为是赠与。甲：目前没有签字文件。'),
        ('unicode','甲😀：第一笔300元。乙：第二笔200元。甲：第二笔尚待核对。'),
    ]
    cases=[]
    for group,text in fixtures:
        case=checked(client.post('/v1/cases',json=dict(title='合成机制夹具 · '+group,description='Synthetic plumbing fixture, never expert Gold')))
        cid=case['id'];doc=checked(client.post('/v1/cases/'+cid+'/documents',files={'file':(group+'.txt',text.encode('utf-8'),'text/plain')}))
        checked(client.post('/v1/cases/'+cid+'/documents/'+doc['id']+'/parse-next',json=dict(pages=3)))
        checked(client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending')))
        cases.append(dict(case_id=cid,document_ids=[doc['id']],case_group_id='synthetic-'+group,split='development',goal='整理原文中的款项与不确定项'))
    return dict(schema_version='paper-experiments.v1',name='Synthetic mechanism smoke',methods=DEFAULT_METHODS,
                model_id='demo',model_revision='demo.v1',law_effective_date='2026-10-28',allow_draft_matter=True,repeats=1,
                budget=dict(max_model_calls=20,max_tool_calls=30,max_input_tokens=1000000,max_output_tokens=40000,max_wall_time_s=180,max_output_per_call=2000),
                options=dict(debate_rounds=1,retrieval_top_k=5,method_options=dict(refinement_rounds=2,retrieval_rounds=3,chunk_chars=4000)),cases=cases)

def run(client,manifest,out,execute=False):
    out.mkdir(parents=True,exist_ok=True)
    if manifest.get('schema_version')!='paper-experiments.v1':raise ValueError('Unsupported manifest schema')
    if type(manifest.get('repeats',1)) is not int or not 1<=manifest.get('repeats',1)<=10:raise ValueError('repeats must be 1..10')
    if not manifest.get('cases') or not manifest.get('methods'):raise ValueError('Cases and methods are required')
    lock=out/'manifest.lock.json'
    if lock.exists() and json.loads(lock.read_text(encoding='utf-8'))!=manifest:raise ValueError('Output folder belongs to another manifest; choose a fresh folder')
    write(lock,manifest)
    source_root=REPO/'product_v1/backend/src/screenshotlegal'
    files=list(source_root.rglob('*.py'))+list(source_root.rglob('*.yaml'))+list((REPO/'paper/experiments').glob('*.py'))
    files += list((REPO/'product_v1/matterpacks').rglob('*.yaml'))
    files += list((REPO/'product_v1/benchmark').glob('*.yaml'))
    source_index={str(p.relative_to(REPO)).replace(chr(92),'/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    source_lock=out/'implementation.sha256.json'
    if source_lock.exists() and json.loads(source_lock.read_text(encoding='utf-8'))!=source_index:
        raise ValueError('Implementation changed since this plan; use a new experiment folder')
    for p in files:
        target=out/'implementation'/p.relative_to(REPO);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    write(source_lock,source_index)
    catalog=checked(client.get('/v1/evaluation/agent-methods'));write(out/'method_registry.json',catalog)
    tasks=[]
    for case in manifest['cases']:
        for repeat in range(manifest.get('repeats',1)):
            for method in manifest['methods']:
                payload=dict(case,name=manifest['name'],method_ids=[method],model_id=manifest['model_id'],model_revision=manifest.get('model_revision',''),law_effective_date=manifest['law_effective_date'],allow_draft_matter=manifest.get('allow_draft_matter',False),budget=manifest['budget'],**manifest.get('options',{}))
                payload['idempotency_key']='paper.'+digest([manifest,case,repeat,method])
                payload=ExperimentCreate.model_validate(payload).model_dump(mode='json')
                tid=digest([case['case_group_id'],case['case_id'],repeat,method])[:24]
                tasks.append(dict(task_id=tid,reproduction_name=METHOD_MODULES[method],case_group_id=case['case_group_id'],case_id=case['case_id'],method_id=method,repeat=repeat,payload=payload))
    if len({t['task_id'] for t in tasks})!=len(tasks):raise ValueError('Duplicate case/method tasks in manifest')
    write(out/'planned_tasks.json',tasks)  # Denominator is fixed before any execution.
    for task in tasks:
        old=read_record(out,task)
        if old is not None:
            if old.get('status') not in {'planned','submitted','running'}:continue
        else:old={}
        record={k:v for k,v in task.items() if k!='payload'}
        try:
            preview=checked(client.post('/v1/evaluation/agent-preview',json=task['payload']))
            if old.get('preview',{}).get('input_digest') not in {None,preview['input_digest']}:raise ValueError('Input changed since frozen plan')
            record.update(status='planned',preview=preview);save_record(out,task,record)
            if not execute:continue
            payload=dict(task['payload'],expected_input_digest=preview['input_digest'])
            # Idempotency makes a resumed client recover the same job; unknown jobs are never retried.
            cohort=checked(client.post('/v1/evaluation/agent-runs',json=payload));rid=cohort['run_ids'][0]
            record.update(status='submitted',run_id=rid);save_record(out,task,record)
            deadline=time.monotonic()+manifest['budget'].get('max_wall_time_s',180)+60
            while True:
                result=checked(client.get('/v1/evaluation/agent-runs/'+rid))
                status=result['run']['status']
                if status not in {'queued','running'}:break
                if time.monotonic()>deadline:
                    record.update(status='running',note='Polling stopped; resume to retrieve this same job. No new call was created.')
                    break
                time.sleep(.1 if manifest['model_id']=='demo' else 1)
            if status not in {'queued','running'}:record.update(status=status,result=result)
        except (ValueError,KeyError) as error:
            record.update(status='blocked_prerequisite' if not record.get('run_id') else 'collection_failed',error=str(error))
        save_record(out,task,record)
        print(METHOD_MODULES[task['method_id']],task['case_group_id'],record['status'],flush=True)
    return summarize(out)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['demo','plan','execute','summarize'])
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--server',default='http://127.0.0.1:18430')
    args=parser.parse_args()
    if args.mode=='summarize':result=summarize(args.out)
    elif args.mode=='demo':
        with demo_client() as client:result=run(client,demo_manifest(client),args.out,True)
    else:
        if not args.manifest:parser.error('--manifest is required')
        import httpx
        manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
        with httpx.Client(base_url=args.server,timeout=60,follow_redirects=False) as client:
            checked(client.post('/v1/auth/login',json=dict(username=os.environ['SCREENSHOTLEGAL_USER'],password=os.environ['SCREENSHOTLEGAL_PASSWORD'])))
            result=run(client,manifest,args.out,args.mode=='execute')
    print(json.dumps(dict(planned=result['planned'],statuses=result['statuses'],method_reports={m['reproduction_name']:'methods/'+m['reproduction_name']+'/'+m['reproduction_name']+'.REPORT.md' for m in result['methods']}),ensure_ascii=False))

if __name__=='__main__':main()
