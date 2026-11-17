"""Small real provider comparison on a common, frozen task cohort."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub import benchmark as b

RUN = b.ART/'runs'/'20261004-vision-pilot'
CONFIG = ROOT/'configs/models.local.yaml'


def ordered(rows):
    return sorted(rows,key=lambda x:hashlib.sha256(('v1-pilot-20261004:'+x['id']).encode()).hexdigest())


def cohort():
    manifest,tasks=b.dataset();selected=[]
    groups=defaultdict(list)
    for task in tasks:groups[task['track']].append(task)
    # Balance categorical tracks across observed gold labels; keep source records.
    for track in ['classification','evidence','chat_type']:
        by_label=defaultdict(list)
        for task in groups[track]:by_label[str(task['answer'])].append(task)
        count=1 if track=='classification' else 2
        for label in sorted(by_label):selected.extend(ordered(by_label[label])[:count])
    for track in ['case_choice','case_open']:
        selected.extend(ordered([x for x in groups[track] if 1<len(x['images'])<=6])[:2])
    selected.extend(ordered(groups['case_single_open'])[:2])
    # Match the same three historical questions in both input protocols.
    questions=[];seen=set()
    for task in ordered(groups['message_grounded']):
        if task['label'] not in seen:
            questions.append(task);seen.add(task['label'])
        if len(questions)==3:break
    indices={x['source_index'] for x in questions}
    selected.extend(questions)
    selected.extend(x for x in groups['message_assisted'] if x['source_index'] in indices)
    selected=sorted(selected,key=lambda x:(x['track'],x['id']))
    spec={'dataset_sha256':manifest['dataset_sha256'],'task_ids':[x['id'] for x in selected],
          'tracks':dict(Counter(x['track'] for x in selected)),
          'method':'Deterministic label-balanced categorical pilot; 2 multi-image cases per case track (2-6 images); 3 distinct message labels with paired protocols. Not a representative full benchmark.'}
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'cohort.json').exists() and b.read(RUN/'cohort.json')!=spec:
        raise ValueError('Cohort changed; use a new pilot directory')
    b.write(RUN/'cohort.json',spec)
    return manifest,selected


def setup():
    probe=b.read(ROOT/'reports/v1.0.0_provider_probe.json')
    providers={x['provider']:x for x in probe['providers']}
    definitions=[
        ('sf_qwen38_thinking','siliconflow','Qwen/Qwen3.8-27B',{'enable_thinking':True,'thinking_budget':2048},'high','max_tokens'),
        ('sf_qwen3vl_instruct','siliconflow','Qwen/Qwen3-VL-32B-Instruct',{'enable_thinking':False},'high','max_tokens'),
        ('sf_qwen3vl_thinking_native','siliconflow','Qwen/Qwen3-VL-32B-Thinking',{},'high','max_tokens'),
        ('kimi3_low','moonshot','kimi-k3',{'reasoning_effort':'low'},None,'max_completion_tokens'),
        ('kimi26_nonthinking','moonshot','kimi-k2.6',{'thinking':{'type':'disabled'}},None,'max_tokens'),
        ('gpt61sol_low','openai','gpt-6.1-sol',{'reasoning_effort':'low'},'high','max_completion_tokens')]
    models=[]
    for alias,provider,id,params,detail,token_param in definitions:
        info=providers[provider]
        if provider!='openai' and id not in info.get('model_ids',[]):
            raise ValueError(f'Model not in live provider catalog: {id}')
        ref=info.get('credential_source') or info['attempts'][-1]['credential_source']
        if provider=='siliconflow' and (RUN/'siliconflow-key-pool.json').exists():
            successful=[x for x in b.read(RUN/'siliconflow-key-pool.json') if x['prediction']['status']=='ok']
            if successful:ref=successful[-1]['credential_source']
        model={'name':alias,'model_name':id,'provider':provider,'vision':True,'mode':'cloud',
               'base_url':info['base_url'],'credential_source':ref,'max_tokens':4096 if provider in ['moonshot','openai'] else 2048,
               'token_limit_parameter':token_param,'timeout':90,'request_parameters':params}
        if detail:model['image_detail']=detail
        if alias=='sf_qwen3vl_thinking_native':
            model.update(max_tokens=4096,thinking_mode='native_fixed_thinking')
        models.append(model)
    CONFIG.write_text(yaml.safe_dump({'models':models},allow_unicode=True,sort_keys=False),encoding='utf-8')
    cohort()
    print(json.dumps({'models':[x['name'] for x in models],'pilot_tasks':len(cohort()[1])}),flush=True)


def predict(model,key,task):
    row={'id':task['id'],'track':task['track'],'case_id':task['case_id'],'label':task['label'],
         'images':task['images'],'image_hashes':task['image_hashes'],
         'started_at':datetime.now(timezone.utc).isoformat()}
    start=time.monotonic()
    try:
        for path,digest in zip(task['images'],task['image_hashes']):
            if b.sha(ROOT/path)!=digest:raise ValueError('Input image changed')
        row.update(b.infer_detailed(model,key,task['prompt'],[str(ROOT/x) for x in task['images']]))
        try:
            row['answer']=b.parse_answer(row['raw']);row['status']='ok'
            if row.get('finish_reason')=='length':row['status']='truncated'
        except (ValueError,TypeError):row['status']='invalid_format'
    except b.ProviderHTTPError as error:
        row.update(status='error',http_status=error.http_status,error=str(error),provider_error=error.provider_error)
    except Exception as error:
        # Avoid logging connection URLs, credential-bearing headers or reprs.
        row.update(status='error',error_type=type(error).__name__)
    row.setdefault('latency_seconds',time.monotonic()-start)
    return row


def run(alias,smoke=False):
    manifest,tasks=cohort();model,key=b.model_config(CONFIG,alias)
    if smoke:tasks=[next(x for x in tasks if x['track']=='classification')]
    out=RUN/(alias+('-smoke' if smoke else ''));out.mkdir(parents=True,exist_ok=True)
    safe={k:v for k,v in model.items() if k not in ['api_key','api_key_env','credential_source','base_url']}
    safe['provider_endpoint']=model['base_url']
    spec={'dataset_sha256':manifest['dataset_sha256'],'model':safe,'task_ids':[x['id'] for x in tasks],
          'task_prompt_sha256':hashlib.sha256(json.dumps([(x['id'],x['prompt']) for x in tasks],ensure_ascii=False).encode()).hexdigest()}
    if (out/'run.json').exists() and b.read(out/'run.json')!=spec:raise ValueError('Run changed')
    b.write(out/'run.json',spec);predictions=out/'predictions.jsonl'
    done={json.loads(x)['id']:json.loads(x) for x in predictions.read_text(encoding='utf-8').splitlines()} if predictions.exists() else {}
    for task in tasks:
        if task['id'] in done:continue
        row=predict(model,key,task)
        with predictions.open('a',encoding='utf-8') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(alias,task['track'],task['id'],row['status'],row.get('http_status'),flush=True)
        if row.get('http_status') in [400,401,402,403,404,429]:break
    b.write(out/'status.json',{'finished_at':datetime.now(timezone.utc).isoformat(),'planned':len(tasks)})
    b.report(out)
    return alias


def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['setup','smoke','run'])
    parser.add_argument('--models',default='sf_qwen38_thinking,sf_qwen3vl_instruct,sf_qwen3vl_thinking_native,kimi3_low,kimi26_nonthinking,gpt61sol_low')
    args=parser.parse_args()
    if args.command=='setup':setup();return
    b.check()
    aliases=args.models.split(',')
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda alias:run(alias,args.command=='smoke'),aliases))
    print(json.dumps({'completed':results}),flush=True)


if __name__=='__main__':main()
