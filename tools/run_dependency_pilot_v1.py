"""Run a frozen 32-request development pilot without reviewer data leakage."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub.benchmark import infer_detailed, model_config, ProviderHTTPError


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def lines(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
def put(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def put_lines(path,rows):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')


def plan(dataset):
    tasks=lines(dataset/'tasks.image_only.jsonl')
    reviews={r['id']:r for r in lines(dataset/'reviewer_only.certification_candidates.jsonl')}
    requests,expected=[],[]
    for task in tasks:
        conditions=[('full',[0,1,2,3])]
        if task['id'].endswith('_base'):
            conditions += [('single_'+role,[i]) for i,role in enumerate(task['roles'])]
            conditions += [('without_'+role,[j for j in range(4) if j!=i]) for i,role in enumerate(task['roles'])]
            conditions += [('question_only',[]),('reverse',[3,2,1,0])]
        for condition,indices in conditions:
            rid=task['id']+'__'+condition
            requests.append({'request_id':rid,'task_id':task['id'],'family_id':task['family_id'],
                'language':task['language'],'condition':condition,'prompt':task['prompt'],
                'images':[task['images'][i] for i in indices],
                'image_hashes':[task['image_hashes'][i] for i in indices],
                'image_roles':[task['roles'][i] for i in indices]})
            roles={task['roles'][i] for i in indices}
            subset=next(s for s in reviews[task['id']]['subset_checks'] if set(s['roles'])==roles)
            expected.append({'request_id':rid,'author_expected_answer':subset['expected_subset_answer'],
                'reference_status':'finite_model_development_oracle_not_legal_gold',
                'possible_full_world_labels':subset['possible_full_world_labels'],
                'professional_signoff':False})
    assert len(requests)==32 and len({r['request_id'] for r in requests})==32
    return requests,expected


def parse(raw,request):
    raw=raw.strip()
    if raw.startswith('```') and raw.endswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
    value=json.loads(raw)
    assert value['answer'] in ['satisfied','not_satisfied','not_established']
    for name in ['identity_alignment','time_condition','legal_conclusion']:
        item=value[name]
        assert isinstance(item['statement'],str) and isinstance(item['evidence_refs'],list)
        for ref in item['evidence_refs']:
            assert ref['image_id'] in {f'P{i}' for i in range(len(request['images']))}
            assert isinstance(ref['quote'],str)
    assert isinstance(value['missing_evidence'],list)
    return value


def attempt(request,model,key,alias,circuit):
    row={k:v for k,v in request.items() if k!='prompt'}
    row.update(model_config=alias,started_at=datetime.now(timezone.utc).isoformat(),api_attempted=False,
               prompt_sha256=hashlib.sha256(request['prompt'].encode()).hexdigest())
    if circuit.is_set():return {**row,'status':'not_attempted','stop_reason':'explicit_quota_or_authentication_failure'}
    try:
        paths=[]
        for path,digest in zip(request['images'],request['image_hashes']):
            assert sha(ROOT/path)==digest
            paths.append(str(ROOT/path))
        row['api_attempted']=True
        result=infer_detailed(model,key,request['prompt'],paths)
        row.update({k:v for k,v in result.items() if k not in ['provider_response','request_id']})
        row['provider_request_id']=result.get('request_id')
        try:
            row['judgments']=parse(result['raw'],request);row['answer']=row['judgments']['answer'];row['status']='ok'
        except (AssertionError,ValueError,TypeError,KeyError):row['status']='invalid_format'
    except ProviderHTTPError as error:
        row.update(status='error',http_status=error.http_status,provider_error=error.provider_error)
        if error.http_status in [401,402] or (error.http_status==429 and (error.provider_error or {}).get('type')=='exceeded_current_quota_error'):circuit.set()
    except Exception as error:row.update(status='error',error_type=type(error).__name__)
    row['finished_at']=datetime.now(timezone.utc).isoformat()
    return row


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--output',required=True)
    p.add_argument('--model',default='sf_qwen38_thinking');p.add_argument('--execute',action='store_true')
    p.add_argument('--historical-scope-probe',action='store_true');args=p.parse_args()
    dataset=(ROOT/args.dataset).resolve();out=(ROOT/args.output).resolve();dataset.relative_to(ROOT);out.relative_to(ROOT)
    if out.exists():raise FileExistsError('Use a new output directory.')
    requests,expected=plan(dataset)
    if args.historical_scope_probe:
        requests=[r for r in requests if r['task_id'].endswith('_base') and r['condition'] in ['full','without_bridge','without_dispatch']]
        for request in requests:
            note=('\n范围澄清：本题回顾图中所报告的、已经发生的出库事件，比较该事件发生前的到账金额；'
                  '不是判断现在是否有足够资金可以将来发货。截图一起提供本身不证明属于同一订单。'
                  '请在时间判断里报出事件日期及来源；缺少该日期则写unknown，不以聊天消息日期替代。') if request['language']=='zh' else (
                  '\nScope clarification: retrospectively compare the receipts with the reported handover event that already occurred, '
                  'not funds currently available for a future handover. Being supplied together does not establish that screenshots '
                  'concern the same file. State the handover event date and its source; use unknown if absent, not the chat message date.')
            request['prompt']+=note
            request['request_id']+='__historical_scope_v2'
        expected=[{**e,'request_id':e['request_id']+'__historical_scope_v2'} for e in expected if e['request_id'] in {r['request_id'].removesuffix('__historical_scope_v2') for r in requests}]
        assert len(requests)==len(expected)==6
    model,key=model_config(ROOT/'configs/models.local.yaml',args.model,require_key=args.execute)
    # No reviewer files or filesystem paths are transmitted; infer_detailed receives only prompt and image bytes.
    protected={str(q.relative_to(ROOT)).replace('\\','/'):sha(q) for q in dataset.rglob('*') if q.is_file()}
    safe_keys=['model_name','max_tokens','timeout','request_parameters','image_detail','token_limit_parameter']
    out.mkdir(parents=True,exist_ok=False)
    put(out/'run.json',{'protocol':'historical_scope_v2_probe' if args.historical_scope_probe else 'dependency_pilot_v1','model_config':args.model,'model':{k:model.get(k) for k in safe_keys},
        'planned_requests':len(requests),'selected_after_v1_development_findings':args.historical_scope_probe,'max_attempts':1,'retries':0,'max_workers':2,'development_only':True,
        'professional_legal_scores':None,'no_reviewer_data_in_provider_payload':True,'source_hashes':protected,
        'requests_sha256':hashlib.sha256(json.dumps(requests,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
        'runner_sha256':sha(Path(__file__)),'api_calls_enabled':args.execute})
    put_lines(out/'requests.jsonl',requests);put_lines(out/'expected.reviewer_only.jsonl',expected)
    if not args.execute:print(json.dumps({'dry_run':True,'planned':len(requests),'api_calls':0}));return
    circuit=Event();completed=[]
    with (out/'predictions.jsonl').open('x',encoding='utf-8',newline='\n') as f:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending=[pool.submit(attempt,r,model,key,args.model,circuit) for r in requests]
            for future in as_completed(pending):
                row=future.result();completed.append(row);f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
                print(row['request_id'],row['status'],flush=True)
    after={path:sha(ROOT/path) for path in protected};assert after==protected
    put(out/'source_integrity.json',{'before':protected,'after':after,'unchanged':True})
    refs={e['request_id']:e['author_expected_answer'] for e in expected}
    valid=[r for r in completed if r['status']=='ok']
    summary={'planned_requests':len(requests),'actual_api_attempts':sum(r['api_attempted'] for r in completed),
        'status_counts':dict(Counter(r['status'] for r in completed)),
        'development_label_agreement':{'agreed':sum(r['answer']==refs[r['request_id']] for r in valid),'valid_denominator':len(valid)},
        'agreement_is_not_legal_accuracy':True,'professional_signoff':False,'original_dataset_files_unchanged':True,
        'reported_successful_usage':{k:sum(r.get('usage',{}).get(k,0) for r in valid) for k in ['prompt_tokens','completion_tokens','total_tokens']},
        'failed_request_usage_unknown':True}
    put(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
