"""Budgeted real execution of the pinned Self-Refine author controller.

The native child never receives the supplier API key. Production settings are read
only; all model requests use the product gateway and an isolated durable ledger.
"""
import argparse
import asyncio
from contextlib import closing
import json
from http.server import BaseHTTPRequestHandler,HTTPServer
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import threading
from types import SimpleNamespace
import uuid

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/'product_v1/backend/src'))
from screenshotlegal.settings import Settings
from screenshotlegal.application.services.preferences import Preferences
from screenshotlegal.research.store import Store
from screenshotlegal.research.gateway import Gateway

MODEL_ID='239c04e4-0ead-568d-8567-3ed9c8ef8c18'
MAX_NEW_CALLS=4

class ReadOnlyConfiguration:
    def __init__(self,folder):self.uri=(folder/'screenshotlegal.sqlite3').resolve().as_uri()+'?mode=ro'
    def get(self,table,id):
        if table not in {'model_configs','auth_users'}:raise ValueError('Unapproved configuration read')
        with closing(sqlite3.connect(self.uri,uri=True)) as db:row=db.execute('SELECT body FROM '+table+' WHERE id=?',(id,)).fetchone()
        if row is None:raise KeyError('Configuration not found')
        return json.loads(row[0])

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--format-adapted',action='store_true')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    approved_out=REPO/'paper/author_reproductions/self_refine/runs/2026-10-28-native-acronym'
    if args.execute and out!=approved_out.resolve():raise PermissionError('The additional four-call authorization is bound to the approved output ledger')
    native_python=REPO/'paper/.author_reproduction_env/Scripts/python.exe'
    driver=Path(__file__).with_name('driver.py')
    if not args.execute:
        subprocess.run([str(native_python),'-B',str(driver),'--out',str(out)],check=True);return
    runtime=out/'.runtime';runtime.mkdir(exist_ok=True)
    phase_out=out/'format_adapted' if args.format_adapted else out
    phase_out.mkdir(exist_ok=True)
    saved_execution=phase_out/'execution.json'
    if saved_execution.exists():
        saved=json.loads(saved_execution.read_text(encoding='utf-8'))
        print(json.dumps(dict(saved,reused_saved_execution=True),ensure_ascii=False))
        raise SystemExit(saved['exit_code'])
    (out/'.gitignore').write_text('.runtime/\n',encoding='utf-8')
    configuration=ReadOnlyConfiguration(REPO/'product_v1/data')
    config=configuration.get('model_configs',MODEL_ID);owner=config['owner_id']
    if not config['allow_external_egress'] or not configuration.get('auth_users',owner).get('enabled'):raise PermissionError('Model/owner not enabled')
    old_ledger=REPO/'paper/experiments/results/2026-10-28-deepseek-pilot/.runtime/research/research.sqlite3'
    with closing(sqlite3.connect(old_ledger.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        prior=db.execute('SELECT COUNT(*) FROM records WHERE kind=?',('evaluation.request',)).fetchone()[0]
    if prior!=45:raise ValueError('Prior authorized pilot count changed; audit before proceeding')
    store=Store(runtime)
    preferences=Preferences(Settings(data_dir=REPO/'product_v1/data'),configuration,owner)
    workspace=SimpleNamespace(preferences=lambda user_id:preferences)
    gateway=Gateway(store,workspace);model=gateway.freeze(owner,MODEL_ID)
    model['parameters']['enable_thinking']=False
    token=secrets.token_urlsafe(32);trace=[]
    (out/'authorization.json').write_text(json.dumps(dict(user_authorized_additional_calls=4,approval='批准额外最多4次，使用现有DeepSeek',
        prior_pilot_calls=prior,max_cumulative_calls=49,task='One original Self-Refine acronym example, two attempts',actual_model=model['model']),ensure_ascii=False,indent=2),encoding='utf-8')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            def respond(code,payload):
                body=json.dumps(payload,ensure_ascii=False).encode()
                self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            if self.headers.get('Authorization')!='Bearer '+token or self.path!='/v1/chat/completions':
                respond(403,dict(error=dict(message='Unauthorized local request',type='invalid_request_error')));return
            requests=store.list('evaluation.request',owner)
            if len(requests)>=MAX_NEW_CALLS:
                respond(400,dict(error=dict(message='Approved author run call cap exhausted',type='invalid_request_error')));return
            if not configuration.get('auth_users',owner).get('enabled') or not configuration.get('model_configs',MODEL_ID)['allow_external_egress']:
                respond(400,dict(error=dict(message='Model access revoked',type='invalid_request_error')));return
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            request_id='author.self_refine.'+str(len(requests)+1)+'.'+uuid.uuid4().hex
            snapshot=dict(model,parameters=dict(model['parameters'],temperature=payload.get('temperature',.7),max_tokens=min(payload.get('max_tokens',300),300)))
            if payload.get('stop'):snapshot['parameters']['stop']=payload['stop']
            messages=payload['messages']
            if args.format_adapted:
                stage=len(trace)
                guidance=[
                    'Continue only the final title in the few-shot examples. Return exactly: Acronym: <one acronym>. Do not repeat the example list or explain.',
                    'Evaluate only the final title and acronym. Return Scores: followed by five short rubric lines and Total score: <integer>/25. Do not repeat examples.',
                    'Use the supplied feedback to revise only the final title/acronym. Return exactly two lines: Title: <new title> and Acronym: <new acronym>. Do not repeat examples.'
                ][stage]
                messages=[dict(m) for m in messages]
                messages[0]=dict(role='system',content=messages[0]['content']+' '+guidance)
            native_payload=json.loads(json.dumps(payload))
            print('AUTHOR_REQUEST',len(requests)+1,'/',MAX_NEW_CALLS,flush=True)
            try:
                response=asyncio.run(gateway.call(owner,snapshot,messages,'author_self_refine',request_id))
                trace.append(dict(request_id=request_id,native_request=native_payload,adapted_messages=messages,response=response))
                (phase_out/'native_trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding='utf-8')
                respond(200,dict(id=request_id,object='chat.completion',model=payload['model'],usage=response.get('usage'),
                    choices=[dict(index=0,finish_reason=response.get('finish_reason'),message=dict(role='assistant',content=response['raw']))]))
            except Exception as error:
                trace.append(dict(request_id=request_id,native_request=payload,error_type=type(error).__name__))
                (phase_out/'native_trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding='utf-8')
                respond(400,dict(error=dict(message='Supplier request failed; no automatic retry',type='invalid_request_error')))
    server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    child_environment=os.environ.copy()
    for key in ['OPENAI_API_KEY','ANTHROPIC_API_KEY','DEEPSEEK_API_KEY','OPENAI_ORG']:child_environment.pop(key,None)
    child_environment.update(AUTHOR_REPRO_BROKER_URL='http://127.0.0.1:'+str(server.server_port)+'/v1',AUTHOR_REPRO_BROKER_TOKEN=token)
    try:
        command=[str(native_python),'-B',str(driver),'--out',str(phase_out),'--execute']
        if args.format_adapted:command.append('--one-revision')
        process=subprocess.run(command,
                               cwd=str(REPO/'paper/upstream_sources/self_refine'),env=child_environment,text=True,encoding='utf-8',
                               errors='replace',capture_output=True,timeout=180)
        (phase_out/'native_stdout.log').write_text(process.stdout,encoding='utf-8')
        (phase_out/'native_stderr.log').write_text(process.stderr,encoding='utf-8')
        requests=store.list('evaluation.request',owner)
        usage=[r.get('response') or r.get('error',{}).get('evidence') or {} for r in requests]
        accounting=dict(model_requests=len(requests),maximum_new_calls=MAX_NEW_CALLS,cumulative_requests=prior+len(requests),
            status=('author_modules_one_revision_completed_with_model_and_format_adaptation' if args.format_adapted else 'original_controller_completed_with_substituted_model') if process.returncode==0 else 'original_controller_failed',
            exit_code=process.returncode,original_benchmark_reproduced=False,
            input_tokens=sum((u.get('usage') or {}).get('prompt_tokens',0) for u in usage),
            output_tokens=sum((u.get('usage') or {}).get('completion_tokens',0) for u in usage),
            estimated_cost_CNY=sum(u.get('cost_estimate') or 0 for u in usage))
        (phase_out/'execution.json').write_text(json.dumps(accounting,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(accounting,ensure_ascii=False),flush=True)
        if process.returncode:raise SystemExit(process.returncode)
    finally:
        server.shutdown();server.server_close();store.close()

if __name__=='__main__':main()
