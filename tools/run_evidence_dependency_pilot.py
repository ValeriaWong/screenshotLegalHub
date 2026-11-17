"""Bounded development ablations plus separately versioned intermediate probes.

No existing file is rewritten. API calls require --execute. Outputs require a
new directory. Gold/review notes are not part of either provider protocol.
"""
import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub.benchmark import infer_detailed, model_config, ProviderHTTPError

REVIEW = ROOT / 'reports/research/legal_answer_review/20261004_pilot_r1'
DEFAULT_MODELS = ['kimi3_low', 'sf_qwen38_thinking']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def put_lines(path, rows):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def parse(raw):
    text = raw.strip()
    if text.startswith('```json') and text.endswith('```'):
        text = text[7:-3].strip()
    elif text.startswith('```') and text.endswith('```'):
        text = text[3:-3].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('JSON object required')
    return value


def plan():
    tasks = [json.loads(s) for s in (REVIEW/'task_reviews.jsonl').read_text(encoding='utf-8').splitlines()]
    tasks = [t for t in tasks if len(t['images']) > 1]
    requests = []
    conditions = {
        ('case_choice', 29): [('full', [0,1,2,3,4,5]), ('single_0', [0]), ('without_0', [1,2,3,4,5]), ('question_only', [])],
        ('case_choice', 111): [('full', [0,1,2]), ('single_1', [1]), ('question_only', [])],
        ('case_open', 43): [('full', [0,1]), ('single_1', [1]), ('single_0', [0]), ('question_only', [])],
        ('case_open', 59): [('full', [0,1,2,3,4,5]), ('single_5', [5]), ('without_5', [0,1,2,3,4]), ('question_only', [])],
    }
    expectations = []
    for task in tasks:
        for condition, indices in conditions[(task['track'], task['source_index'])]:
            rid = task['id'] + '__legacy__' + condition
            requests.append({'request_id': rid, 'task_id': task['id'], 'protocol': 'legacy_question_unchanged',
                'condition': condition, 'prompt': task['prompt'],
                'images': [task['images'][i] for i in indices],
                'image_hashes': [task['image_hashes'][i] for i in indices]})
            # Reviewer-only, not sent to any provider.
            q = task['source_index']
            if not indices:
                scope = 'insufficient_specific_case_facts'
            elif q == 111:
                scope = 'risk_title_present_criminal_elements_insufficient'
            elif q == 59:
                scope = 'funds_visible_loan_and_identity_not_established'
            elif q == 43 and indices == [0]:
                scope = 'purchase_visible_dispatch_issue_missing'
            else:
                scope = 'possible_relation_or_issue_supported_actual_breach_unknown'
            expectations.append({'request_id': rid, 'reviewer_type': 'AI_development_review',
                'scope': scope, 'numeric_score': None, 'professional_signoff': False})
        refs = '\n'.join(f'P{i}: 第{i+1}个输入图（不是诉讼证据页码）' for i in range(len(task['images'])))
        prompt = task['prompt'] + '\n\n这是独立的结构化研究协议，请以上面原问题为对象，用以下JSON替代原输出格式。'
        prompt += '\n只提交可核查的判断及短引文，不输出自由展开的内部推理过程。没有图示依据时回答unknown，不能以头像/备注直接确认实名或案件事实。'
        prompt += '\n分别填写identity_alignment（双方/跨图身份能否确认），time_condition（与问题相关的时间、条件及是否已满足），legal_conclusion（原问题的潜在法律关系/结论及证据限度）。'
        prompt += '\n每项status只能取supported/partial/unknown/not_applicable，statement为简短判断，evidence_refs为实际输入图的image_id与可见原句quote。不能补造语音或被遮挡文字，不把状态栏时钟当消息时间。不适用的维度说明原因。'
        prompt += '\n图片标识顺序：\n' + refs
        prompt += '\n输出JSON：{"identity_alignment":{"status":"unknown","statement":"...","evidence_refs":[]},"time_condition":{"status":"unknown","statement":"...","evidence_refs":[]},"legal_conclusion":{"status":"partial","statement":"...","evidence_refs":[]},"missing_evidence":[]}'
        rid = task['id'] + '__structured__full'
        requests.append({'request_id': rid, 'task_id': task['id'], 'protocol': 'observable_judgments_v1',
            'condition': 'full', 'prompt': prompt, 'images': task['images'], 'image_hashes': task['image_hashes']})
        expectations.append({'request_id': rid, 'scope': 'separate_identity_time_condition_legal_judgments',
            'reviewer_type': 'AI_development_review', 'numeric_score': None, 'professional_signoff': False})
    return tasks, requests, expectations


def attempt(request, model, key, alias, stopped=None):
    row = {k: request[k] for k in ['request_id','task_id','protocol','condition','images','image_hashes']}
    row.update(model_config=alias, started_at=datetime.now(timezone.utc).isoformat(), api_attempted=False)
    if stopped is not None and stopped.is_set():
        row.update(status='not_attempted', stop_reason='provider_quota_or_authentication_circuit_open')
        return row
    try:
        paths = []
        for path, digest in zip(request['images'], request['image_hashes']):
            if sha(ROOT/path) != digest:
                raise ValueError('Image differs from frozen hash')
            paths.append(str(ROOT/path))
        row['api_attempted'] = True
        result = infer_detailed(model, key, request['prompt'], paths)
        # Store observable answer, usage and request trace, not hidden reasoning.
        row.update({k:v for k,v in result.items() if k not in ['provider_response', 'request_id']})
        row['provider_request_id'] = result.get('request_id')
        try:
            value = parse(result['raw'])
            if request['protocol'] == 'legacy_question_unchanged':
                if 'answer' not in value:
                    raise ValueError('answer key required')
                row['answer'] = value['answer']
            else:
                for field in ['identity_alignment','time_condition','legal_conclusion']:
                    item = value.get(field)
                    if not isinstance(item, dict) or item.get('status') not in ['supported','partial','unknown','not_applicable']:
                        raise ValueError('Invalid judgment field')
                    if not isinstance(item.get('statement'), str) or not isinstance(item.get('evidence_refs'), list):
                        raise ValueError('Invalid judgment statement or references')
                    for ref in item['evidence_refs']:
                        if not isinstance(ref, dict) or ref.get('image_id') not in {f'P{i}' for i in range(len(paths))} or not isinstance(ref.get('quote'), str):
                            raise ValueError('Invalid evidence reference')
                if not isinstance(value.get('missing_evidence'), list):
                    raise ValueError('missing_evidence list required')
                row['judgments'] = value
            row['status'] = 'ok'
        except (ValueError, TypeError):
            row['status'] = 'invalid_format'
    except ProviderHTTPError as error:
        row.update(status='error', http_status=error.http_status, provider_error=error.provider_error)
        if stopped is not None and (error.http_status in [401,402] or
                (error.http_status == 429 and (error.provider_error or {}).get('type') == 'exceeded_current_quota_error')):
            stopped.set()
    except Exception as error:
        row.update(status='error', error_type=type(error).__name__)
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--config', default='configs/models.local.yaml')
    p.add_argument('--models', default=','.join(DEFAULT_MODELS))
    p.add_argument('--execute', action='store_true')
    args = p.parse_args()
    aliases = args.models.split(',')
    if len(aliases) > 2 or len(set(aliases)) != len(aliases):
        raise ValueError('This pilot permits at most two distinct model configurations.')
    tasks, requests, expected = plan()
    assert len(requests) == 19 and len({r['request_id'] for r in requests}) == 19
    models = {a: model_config(ROOT/args.config, a, require_key=args.execute) for a in aliases}
    inputs = {REVIEW/'task_reviews.jsonl', REVIEW/'source_integrity.json'}
    for t in tasks:
        inputs.update(ROOT/i for i in t['images'])
    integrity = json.loads((REVIEW/'source_integrity.json').read_text(encoding='utf-8'))
    inputs.update(ROOT/path for path in integrity['before'])
    for path, digest in integrity['before'].items():
        assert sha(ROOT/path) == digest, 'A source differs from the first review snapshot.'
    before = {str(q.relative_to(ROOT)).replace('\\','/'): sha(q) for q in sorted(inputs)}
    out = Path(args.output).resolve()
    out.relative_to(ROOT)
    if out.exists():
        raise FileExistsError('Use a new output directory; original runs are never overwritten.')
    safe_models = {}
    safe_fields = ['name','model_name','mode','vision','max_tokens','timeout','token_limit_parameter','request_parameters','image_detail']
    for alias, (model, key) in models.items():
        safe_models[alias] = {k:model.get(k) for k in safe_fields}
    spec = {'protocol': 'evidence_dependency_development_r2', 'development_only': True,
        'selected_after_pilot_review': True, 'new_gold_release': False,
        'legacy_requests_per_model': 15, 'structured_requests_per_model': 4,
        'planned_requests': len(requests)*len(aliases), 'max_attempts_per_request': 1,
        'models': safe_models, 'request_sha256': hashlib.sha256(json.dumps(requests,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
        'source_hashes': before, 'api_calls_enabled': args.execute,
        'request_protocols_are_not_pooled_for_accuracy': True}
    out.mkdir(parents=True, exist_ok=False)
    put(out/'run.json', spec)
    put_lines(out/'requests.jsonl', requests)
    put_lines(out/'expected.reviewer_only.jsonl', expected)
    put(out/'source_integrity.before.json', before)
    if not args.execute:
        print(json.dumps({'dry_run': True, 'planned_requests': spec['planned_requests'], 'api_calls': 0}, ensure_ascii=False))
        return
    completed = []
    circuits = {alias: Event() for alias in aliases}
    with (out/'predictions.jsonl').open('x', encoding='utf-8', newline='\n') as log:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = {pool.submit(attempt, req, model, key, alias, circuits[alias]): (alias, req['request_id'])
                for alias, (model,key) in models.items() for req in requests}
            for future in as_completed(pending):
                row = future.result()
                completed.append(row)
                log.write(json.dumps(row, ensure_ascii=False)+'\n')
                log.flush()
                print(row['model_config'], row['request_id'], row['status'], flush=True)
    after = {path: sha(ROOT/path) for path in before}
    put(out/'source_integrity.after.json', {'hashes': after, 'unchanged': before==after})
    summary = {'planned_requests': spec['planned_requests'], 'attempted_requests': len(completed),
        'api_attempts': sum(r['api_attempted'] for r in completed), 'retries': 0, 'original_files_unchanged': before==after,
        'numeric_legal_scores': None, 'professional_signoff': False, 'by_model': {}}
    for alias in aliases:
        items = [r for r in completed if r['model_config']==alias]
        summary['by_model'][alias] = {'planned':len(requests), 'ok':sum(r['status']=='ok' for r in items),
            'invalid_format':sum(r['status']=='invalid_format' for r in items), 'error':sum(r['status']=='error' for r in items),
            'not_attempted':sum(r['status']=='not_attempted' for r in items),
            'usage':{k:sum(r.get('usage',{}).get(k,0) for r in items) for k in ['prompt_tokens','completion_tokens','total_tokens']}}
    put(out/'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert before == after, 'A protected input changed during the run.'


if __name__ == '__main__':
    main()
