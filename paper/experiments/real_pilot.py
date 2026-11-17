"""Run the explicitly authorized 46-call DeepSeek pilot in an isolated application.
The existing model configuration is read-only; keys never enter manifests or logs.
"""
import argparse
import copy
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'product_v1/backend/src'))
from run import checked,run,write
from screenshotlegal.experiments.registry import call_ceiling

MODEL_ID='239c04e4-0ead-568d-8567-3ed9c8ef8c18'
MAX_CALLS=46
FIXTURES=[('simple','甲：收到520元。乙：下周归还。'),('counterevidence','甲：款项是借款。乙：我认为是赠与。甲：目前没有签字文件。')]

class ReadOnlyConfiguration:
    def __init__(self,folder):self.uri=(folder/'screenshotlegal.sqlite3').resolve().as_uri()+'?mode=ro'
    def get(self,table,id):
        if table not in {'model_configs','auth_users'}:raise ValueError('Only authorized configuration/account reads are supported')
        with closing(sqlite3.connect(self.uri,uri=True)) as db:
            row=db.execute('SELECT body FROM '+table+' WHERE id=?',(id,)).fetchone()
        if row is None:raise KeyError('Configuration/account not found')
        return json.loads(row[0])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--stage',choices=['baseline','without-thinking-simple','without-thinking-counter','protocol-simple','protocol-counter'],default='baseline')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source_data=REPO/'product_v1/data';config=ReadOnlyConfiguration(source_data)
    model=config.get('model_configs',MODEL_ID);owner=model['owner_id']
    if not model['allow_external_egress'] or 'DeepSeek' not in model['model_name']:raise ValueError('The authorized DeepSeek configuration is not enabled')
    if not config.get('auth_users',owner).get('enabled'):raise PermissionError('Source model owner is disabled')
    runtime=out/'.runtime';runtime.mkdir(exist_ok=True)
    (out/'.gitignore').write_text('.runtime/\n',encoding='utf-8')
    os.environ['DATA_DIR']=str(runtime)
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(REPO/'product_v1/backend/alembic.ini')),'head')
    from fastapi.testclient import TestClient
    from screenshotlegal.settings import Settings
    from screenshotlegal.application.services.preferences import Preferences
    from screenshotlegal.research.gateway import ModelFailure
    from screenshotlegal.api.main import create_app,app as bootstrap_app
    settings=Settings(data_dir=runtime);source_settings=Settings(data_dir=source_data)
    app=create_app(settings)
    class AuthorizedPreferences(Preferences):
        def owned(self,id):
            if id!=MODEL_ID:raise PermissionError('This pilot is limited to the approved model')
            if not config.get('auth_users',owner).get('enabled'):raise PermissionError('Model owner is disabled')
            return super().owned(id)
    def preferences(user_id):
        if user_id!=owner:raise PermissionError('Unexpected pilot account')
        return AuthorizedPreferences(source_settings,config,owner)
    app.state.workspace.preferences=preferences
    store=app.state.research['store'];gateway=app.state.research['gateway'];original_call=gateway.call
    async def capped_call(user_id,snapshot,messages,purpose,request_id):
        if snapshot['config_id']!=MODEL_ID:raise PermissionError('Unapproved model')
        # Gateway persists evaluation.request before awaiting HTTP. One worker runs
        # this isolated database; this cap also survives process restarts.
        calls=store.list('evaluation.request',owner)
        if len(calls)>=MAX_CALLS:raise ModelFailure('global_budget_exhausted','Approved 46-call pilot limit reached')
        write(out/'call_progress.json',dict(limit=MAX_CALLS,previous_requests=len(calls),next_request_id=request_id))
        print('MODEL_REQUEST',len(calls)+1,'/',MAX_CALLS,request_id,flush=True)
        return await original_call(user_id,snapshot,messages,purpose,request_id)
    gateway.call=capped_call
    password_file=runtime/'pilot-login.secret'
    if not password_file.exists():password_file.write_text(secrets.token_urlsafe(36),encoding='utf-8')
    login=dict(username=owner,password=password_file.read_text(encoding='utf-8'))
    try:
        with TestClient(app) as client:
            initialized=checked(client.get('/v1/auth/status'))['initialized']
            checked(client.post('/v1/auth/login' if initialized else '/v1/auth/setup',json=login if initialized else dict(login,display_name='Authorized isolated paper pilot')))
            manifest_path=out/'pilot.manifest.json'
            if manifest_path.exists():manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
            else:
                cases=[]
                for name,text in FIXTURES:
                    cid=checked(client.post('/v1/cases',json=dict(title='真实模型开发夹具 · '+name,description='Synthetic development fixture; no expert Gold')))['id']
                    doc=checked(client.post('/v1/cases/'+cid+'/documents',files={'file':(name+'.txt',text.encode('utf-8'),'text/plain')}))
                    checked(client.post('/v1/cases/'+cid+'/documents/'+doc['id']+'/parse-next',json=dict(pages=3)))
                    checked(client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending')))
                    (out/'inputs').mkdir(exist_ok=True);(out/'inputs'/(name+'.txt')).write_bytes(text.encode('utf-8'))
                    cases.append(dict(case_id=cid,document_ids=[doc['id']],case_group_id='deepseek-pilot-'+name,split='development',goal='整理原文中的款项与不确定项'))
                manifest=dict(schema_version='paper-experiments.v1',name='Authorized DeepSeek development pilot',methods=['E03','E11','E18','E20'],model_id=MODEL_ID,model_revision=model['model_name'],law_effective_date='2026-10-28',allow_draft_matter=True,repeats=1,
                    budget=dict(max_model_calls=9,max_tool_calls=16,max_input_tokens=200000,max_output_tokens=36000,max_wall_time_s=300,max_output_per_call=4000),
                    options=dict(debate_rounds=1,retrieval_top_k=5,method_options=dict(refinement_rounds=2,retrieval_rounds=3,chunk_chars=4000)),cases=cases)
                write(manifest_path,manifest)
            stage_out=out
            if args.stage!='baseline':
                manifest=copy.deepcopy(manifest)
                manifest['name']='Explicit thinking disabled development verification · '+args.stage
                manifest['options']['inference_options']=dict(enable_thinking=False)
                manifest['cases']=[manifest['cases'][0 if args.stage.endswith('simple') else 1]]
                if args.stage in {'without-thinking-counter','protocol-simple'}:manifest['methods']=['E03']
                if args.stage=='protocol-counter':manifest['methods']=['E11']
                stage_out=out/args.stage
            options=manifest['options']['method_options']|{k:manifest['options'][k] for k in ['debate_rounds','retrieval_top_k']}
            ceilings={m:call_ceiling(m,manifest['budget'],options,[100]) for m in manifest['methods']}
            planned=sum(ceilings.values())*len(manifest['cases'])*manifest['repeats']
            spent=len(store.list('evaluation.request',owner))
            if args.stage!='baseline' and planned>MAX_CALLS-spent:raise ValueError('Verification plan exceeds remaining authorized calls')
            if planned>MAX_CALLS:raise ValueError('Plan exceeds the authorized total call limit')
            write(stage_out/'authorization.json',dict(user_authorized=True,authorization='使用已启用的 DeepSeek，最多46次调用',scope='Two-fixture authorized pilot; phase '+args.stage,max_calls=MAX_CALLS,planned_call_ceiling=planned,method_call_ceilings=ceilings,model={k:model.get(k) for k in ['id','name','model_name','owner_id','allow_external_egress','input_token_price','output_token_price','price_currency']}))
            result=run(client,manifest,stage_out,args.execute)
            requests=store.list('evaluation.request',owner)
            write(stage_out/'call_accounting.json',dict(limit=MAX_CALLS,total_pilot_requests=len(requests),phase_requests=len(requests)-spent,within_limit=len(requests)<=MAX_CALLS,request_ids=[r['id'] for r in requests]))
            print(json.dumps(dict(planned=result['planned'],statuses=result['statuses'],requests=len(requests),within_limit=len(requests)<=MAX_CALLS),ensure_ascii=False),flush=True)
    finally:
        for instance in [app,bootstrap_app]:
            instance.state.research['store'].close();instance.state.workspace.repo.engine.dispose()

if __name__=='__main__':main()
