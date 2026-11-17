"""Versioned screening protocol, case-group holdout, actual bounded model runs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub import benchmark as b
from legalhub.inference import predict

BASE = b.ART / 'iterations' / '20261004-p2'
ALIASES = ['sf_qwen38_thinking', 'sf_qwen3vl_thinking_native', 'kimi3_low']
PROTOCOL = 'p2-screening-definitions-20261004'
REPORT_PREFIX = 'v1.0.0_iteration_p2_'
EXTRA_DEV_GROUPS = set()
EVIDENCE_NOTE = 'Evidence definitions are a documented operational interpretation of archive screening rules, not validated original annotator instructions.'
CASE_CARRYOVER = None
SPACES = {
    'classification': ['legal_dialog', 'not_dialog_but_legal', 'non_legal_dialog', 'not_dialog_and_non_legal', 'unknown'],
    'evidence': ['is_evidence', 'not_evidence', 'unknown'],
    'chat_type': ['private_chat', 'group_chat', 'unknown'],
}
DEFINITIONS = '''只根据截图作三项独立判断，不读取或猜测未提供的案情。
classification：legal_dialog=聊天且可见法律相关事实/权利义务表达；not_dialog_but_legal=非聊天但具有法律相关内容；non_legal_dialog=聊天但无可见法律相关内容；not_dialog_and_non_legal=非聊天且无可见法律相关内容。
evidence：本次是截图证据材料筛选标签，不评价法律上的真实性、合法性或可采性。is_evidence=存在可辨识、与争议事实或权利义务有关的信息/行为，可作为待审核证据线索；not_evidence=仅闲聊、玩笑、无关广告或没有可辨识的相关信息。不能因为“任何截图理论上都可能是证据”就全部选择is_evidence。借款、承诺、转账等须结合图中上下文，不强行推定双方身份。
chat_type：group_chat=可见多人会话界面或群成员发言；private_chat=可见双人会话界面。非聊天或看不清时为unknown。
任一字段依据不足时使用unknown。只输出JSON，格式：{"answer":{"classification":"标签","evidence":"标签","chat_type":"标签"}}。'''


def order(rows):
    return sorted(rows, key=lambda x: hashlib.sha256(('p2-20261004:' + x['id']).encode()).hexdigest())


def prepare():
    manifest, old = b.dataset()
    pilot_ids = set(b.read(b.ART / 'runs/20261004-vision-pilot/cohort.json')['task_ids'])
    dev_groups = {x['case_id'] for x in old if x['id'] in pilot_ids}
    # All siblings of a pilot case stay in development. More deterministic groups for development.
    dev_groups |= {x['case_id'] for x in old if int(hashlib.sha256(x['case_id'].encode()).hexdigest()[:8], 16) % 10 == 0}
    dev_groups |= EXTRA_DEV_GROUPS
    by_image = defaultdict(dict)
    issues = []
    for t in old:
        if t['track'] in SPACES:
            k = t['images'][0]
            if t['track'] in by_image[k] and by_image[k][t['track']]['answer'] != t['answer']:
                issues.append({'image': k, 'reason': 'conflicting_duplicate_tag', 'track': t['track']})
                by_image[k]['conflict'] = True
            else:
                by_image[k][t['track']] = t
    tasks = []
    for image, fields in by_image.items():
        if fields.get('conflict') or not all(k in fields for k in SPACES):
            continue
        t = fields['classification']
        tasks.append({'id': 'screening-' + hashlib.sha256(image.encode()).hexdigest()[:20],
                      'track': 'screening_bundle', 'case_id': t['case_id'], 'images': t['images'],
                      'image_hashes': t['image_hashes'], 'prompt': DEFINITIONS,
                      'answer': {k: fields[k]['answer'] for k in SPACES}, 'answer_spaces': SPACES,
                      'legacy_task_ids': [fields[k]['id'] for k in SPACES],
                      'split': 'development' if t['case_id'] in dev_groups else 'holdout',
                      'gold_status': 'historical_not_independently_revalidated'})
    chosen = []
    for split, limit in [('development', 12), ('holdout', 200)]:
        pool = order([x for x in tasks if x['split'] == split])
        selected = {}
        # Ensure rare image classes and group chats are represented; retain full distribution metadata.
        for field, labels, quota in [('classification', SPACES['classification'][:-1], 12 if split == 'holdout' else 2),
                                     ('evidence', SPACES['evidence'][:-1], 20 if split == 'holdout' else 2),
                                     ('chat_type', ['group_chat'], 16 if split == 'holdout' else 2)]:
            for label in labels:
                matches = [x for x in pool if x['answer'][field] == label]
                for x in matches[:quota]:
                    selected[x['id']] = x
        for x in pool:
            if len(selected) >= limit:
                break
            selected[x['id']] = x
        chosen.extend(list(selected.values())[:limit])
    # Case-choice inputs have not changed. Additional screenshot-audit groups affect screening only.
    case_dev_groups = {x['case_id'] for x in old if x['id'] in pilot_ids} | {x['case_id'] for x in old if int(hashlib.sha256(x['case_id'].encode()).hexdigest()[:8], 16) % 10 == 0}
    cases = [dict(x, split='development' if x['case_id'] in case_dev_groups else 'holdout',
                  gold_status='historical_not_independently_revalidated') for x in old if x['track'] == 'case_choice' and 1 < len(x['images']) <= 6]
    for split, limit in [('development', 2), ('holdout', 30)]:
        chosen.extend(order([x for x in cases if x['split'] == split])[:limit])
    chosen.sort(key=lambda x: (x['split'], x['track'], x['id']))
    blob = ''.join(json.dumps(x, ensure_ascii=False, sort_keys=True) + '\n' for x in chosen).encode()
    spec = {'protocol': PROTOCOL, 'dataset_sha256': hashlib.sha256(blob).hexdigest(),
            'legacy_dataset_sha256': manifest['dataset_sha256'], 'tasks': len(chosen),
            'splits': dict(Counter(x['split'] for x in chosen)), 'tracks': dict(Counter(x['track'] for x in chosen)),
            'split_groups': {s: sorted({x['case_id'] for x in chosen if x['split'] == s}) for s in ('development', 'holdout')},
            'notes': ['Filename groups are provisional case identifiers.', 'Labels unchanged; new input protocol.',
                      'Screening bundles share an image and are not independent trials.',
                      EVIDENCE_NOTE,
                      'Historical gold requires human audit; not a professional legal correctness benchmark.'],
            'quarantined': issues,
            'label_distribution': {s: {k: dict(Counter(x['answer'][k] for x in chosen if x['split'] == s and x['track'] == 'screening_bundle')) for k in SPACES} for s in ('development', 'holdout')}}
    BASE.mkdir(parents=True, exist_ok=True)
    if (BASE / 'manifest.json').exists() and b.read(BASE / 'manifest.json') != spec:
        raise ValueError('Frozen iteration changed; choose a new version')
    (BASE / 'tasks.jsonl').write_bytes(blob)
    b.write(BASE / 'manifest.json', spec)
    # Queue legacy message tasks for definition/context review; do not silently delete from original benchmark.
    review = [{'id': t['id'], 'label': t['label'], 'answer': t['answer'], 'images': t['images'],
               'reason': 'needs_field_definition_and_context_audit'} for t in old if t['track'] == 'message_grounded' and t['id'] in pilot_ids]
    b.write(BASE / 'message_review_queue.json', review)
    print(json.dumps({'prepared': spec['tasks'], 'splits': spec['splits'], 'sha256': spec['dataset_sha256']}), flush=True)


def load():
    m = b.read(BASE / 'manifest.json')
    if b.sha(BASE / 'tasks.jsonl') != m['dataset_sha256']:
        raise ValueError('Iteration digest mismatch')
    tasks = [json.loads(x) for x in (BASE / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
    for track in ('screening_bundle', 'case_choice'):
        assert not {x['case_id'] for x in tasks if x['split']=='development' and x['track']==track} & {x['case_id'] for x in tasks if x['split']=='holdout' and x['track']==track}
    return m, tasks


def configured(alias, structured):
    model, key = b.model_config(ROOT / 'configs/models.local.yaml', alias)
    model = dict(model, request_parameters=dict(model.get('request_parameters', {})))
    model['timeout'] = 90
    if structured:
        model['request_parameters']['response_format'] = {'type': 'json_object'}
        # Actual development preflight: native Thinking rejects response_format (HTTP 400).
        # Its fixed reasoning mode still runs, with an explicit JSON-only prompt.
        if alias == 'sf_qwen3vl_thinking_native':
            model['request_parameters'].pop('response_format', None)
            model['structured_output_capability'] = 'unsupported_in_development_preflight'
    return model, key


def run(args):
    manifest, tasks = load()
    tasks = [x for x in tasks if x['split'] == args.split]
    if args.limit:
        tasks = tasks[:args.limit]
    if not args.execute:
        print(json.dumps({'dry_run': True, 'tasks_per_model': len(tasks), 'models': args.models, 'split': args.split})); return
    jobs = []
    outputs = {}
    models = {}
    for alias in args.models.split(','):
        model, key = configured(alias, args.structured)
        out = BASE / 'runs' / (args.split + ('-structured' if args.structured else '-prompt') + args.run_tag) / alias
        safe = {k: v for k, v in model.items() if k not in ('api_key', 'api_key_env', 'credential_source', 'base_url')}
        spec = {'dataset_sha256': manifest['dataset_sha256'], 'model': safe, 'task_ids': [x['id'] for x in tasks], 'split': args.split,
                'retries': 2, 'structured_output': args.structured,
                'credential_source': model.get('credential_source', {}), 'run_tag': args.run_tag}
        if (out / 'run.json').exists() and b.read(out / 'run.json') != spec:
            raise ValueError('Resume settings changed')
        b.write(out / 'run.json', spec)
        p = out / 'predictions.jsonl'
        if CASE_CARRYOVER and args.split == 'holdout' and not p.exists():
            origin = CASE_CARRYOVER / alias
            origin_spec = b.read(origin / 'run.json')
            if origin_spec['model'] != safe:
                raise ValueError('Carryover model configuration differs')
            source_tasks = {x['id']: x for x in [json.loads(s) for s in (CASE_CARRYOVER.parents[1] / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]}
            desired = {x['id']:x for x in tasks if x['track']=='case_choice'}
            source = origin / 'predictions.jsonl'
            for line in source.read_text(encoding='utf-8').splitlines():
                row = json.loads(line)
                if row['id'] not in desired: continue
                if source_tasks[row['id']] != desired[row['id']]:
                    raise ValueError('Carryover task input/gold differs')
                row['carried_over_from'] = {'path': source.relative_to(ROOT).as_posix(), 'sha256': b.sha(source)}
                with p.open('a', encoding='utf-8') as stream: stream.write(json.dumps(row, ensure_ascii=False)+'\n')
        done = {json.loads(x)['id'] for x in p.read_text(encoding='utf-8').splitlines()} if p.exists() else set()
        outputs[alias] = p; models[alias] = (model, key)
        jobs.extend((alias, x) for x in tasks if x['id'] not in done)
    # Interleave providers and keep at most two in-flight calls for one model.
    jobs.sort(key=lambda j: (j[1]['id'], j[0]))
    from threading import Semaphore
    gates = {a: Semaphore(2) for a in models}
    def execute(job):
        a, task = job
        with gates[a]:
            row = predict(*models[a], task)
        return a, row
    blocked = set()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        # Bounded submission permits fatal configuration errors to stop further spending.
        pending = {}; cursor = 0
        while cursor < len(jobs) or pending:
            while cursor < len(jobs) and len(pending) < args.workers:
                job = jobs[cursor]; cursor += 1
                if job[0] not in blocked:
                    pending[pool.submit(execute, job)] = job
            if not pending: continue
            future = next(as_completed(pending)); pending.pop(future)
            alias, row = future.result()
            with outputs[alias].open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            print(alias, row['id'], row['status'], row.get('http_status'), len(row['attempts']), flush=True)
            if row.get('http_status') in (400, 401, 402, 403, 404):
                blocked.add(alias)
    report(args.split, args.structured, args.run_tag)


def report(split, structured, run_tag=''):
    manifest, tasks = load(); tasks = [x for x in tasks if x['split'] == split]
    folder = BASE / 'runs' / (split + ('-structured' if structured else '-prompt') + run_tag)
    summaries = []
    for out in sorted(folder.iterdir()) if folder.exists() else []:
        if not (out / 'run.json').exists(): continue
        spec = b.read(out / 'run.json'); planned = [x for x in tasks if x['id'] in spec['task_ids']]
        predictions = {x['id']: x for x in [json.loads(s) for s in (out / 'predictions.jsonl').read_text(encoding='utf-8').splitlines()]} if (out / 'predictions.jsonl').exists() else {}
        metrics = {}
        for field in list(SPACES) + ['case_choice']:
            cohort = [t for t in planned if t['track'] == ('case_choice' if field == 'case_choice' else 'screening_bundle')]
            pairs = []
            for t in cohort:
                p = predictions.get(t['id'], {'status': 'missing'})
                answer = p.get('answer', {}).get(field) if field != 'case_choice' and p.get('status') == 'ok' else p.get('answer') if field == 'case_choice' else None
                gold = t['answer'][field] if field != 'case_choice' else t['answer']
                pairs.append(({'answer': gold}, {'answer': answer, 'status': p['status']}))
            if pairs:
                metric = {'planned': len(pairs), 'correct': sum(p['status'] == 'ok' and b.normalize(p['answer']) == b.normalize(t['answer']) for t, p in pairs)}
                metric['accuracy'] = metric['correct'] / len(pairs)
                if field != 'case_choice':
                    metric.update(b.categorical_metrics(pairs))
                    metric['prediction_distribution'] = dict(Counter(str(p['answer']) if p['status'] == 'ok' else p['status'] for _, p in pairs))
                metrics[field] = metric
        responses = [x for x in predictions.values() if x.get('http_status') == 200]
        lat = sorted(x['latency_seconds'] for x in responses)
        summary = {'alias': out.name, 'model': spec['model'], 'planned': len(planned), 'attempted': len(predictions),
                   'statuses': dict(Counter(predictions.get(x['id'], {'status': 'missing'})['status'] for x in planned)),
                   'first_attempt_success': sum(x.get('first_attempt_success', False) for x in predictions.values()),
                   'carried_over_tasks': sum(bool(x.get('carried_over_from')) for x in predictions.values()),
                   'http200_after_retries': len(responses), 'attempts': sum(len(x['attempts']) for x in predictions.values()),
                   'success_latency_p50': statistics.median(lat) if lat else None,
                   'success_latency_p95': lat[max(0, __import__('math').ceil(.95 * len(lat)) - 1)] if lat else None,
                   'total_request_elapsed_seconds': sum(x.get('elapsed_seconds', 0) for x in predictions.values()),
                   'usage': {k: sum(a.get('usage', {}).get(k, 0) for x in predictions.values() for a in x['attempts']) for k in ('prompt_tokens', 'completion_tokens')},
                   'metrics': metrics}
        summaries.append(summary); b.write(out / 'metrics.json', summary)
    result = {'manifest': manifest, 'split': split, 'structured': structured, 'runs': summaries}
    b.write(BASE / (split + ('-structured' if structured else '-prompt') + run_tag + '-results.json'), result)
    target = ROOT / 'reports' / (REPORT_PREFIX + split + ('_structured' if structured else '_prompt') + run_tag + '.md')
    lines = ['# v1.0.0 第二轮评测', '', f'协议：{manifest["protocol"]}；split：{split}；新数据 SHA256：`{manifest["dataset_sha256"]}`。',
             '', '截图三项标签合并一次视觉请求；不是三个独立样本。原金标未改，标签说明尚非完整人工审核后的金标。', EVIDENCE_NOTE,
             '消息题保留在旧集和审核队列中，未按欠定义问题宣布能力为零。失败、格式错误和未完成都计入分母。', '',
             '| 配置 | 完成/计划 | 有效回答 | 首试响应成功 | 重试后响应成功 | p50秒 | p95秒 |', '|---|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        lines.append(f'| {s["alias"]} | {s["attempted"]}/{s["planned"]} | {s["statuses"].get("ok",0)} | {s["first_attempt_success"]} | {s["http200_after_retries"]} | {s["success_latency_p50"] or 0:.2f} | {s["success_latency_p95"] or 0:.2f} |')
    lines += ['', '| 配置 | 分类准确率/宏F1 | 证据筛选准确率/宏F1 | 群聊私聊准确率/宏F1 | 多图案由选择准确率 |', '|---|---:|---:|---:|---:|']
    for s in summaries:
        cells = [f'{s["metrics"][k]["accuracy"]:.3f}/{s["metrics"][k]["macro_f1"]:.3f}' if k in s['metrics'] else '—' for k in SPACES]
        case = s['metrics'].get('case_choice', {})
        lines.append('| ' + s['alias'] + ' | ' + ' | '.join(cells) + ' | ' + (f'{case["accuracy"]:.3f}' if case else '—') + ' |')
    lines += ['', '样本按文件名前缀组隔离开发/验收，前缀尚未核对为司法案件。类别抽样带有平衡配额，分布见 manifest；不声称是自然总体准确率。',
              '沿用结果数量：'+str({s['alias']:s['carried_over_tasks'] for s in summaries})+'。仅复用输入、金标和配置完全相同的多图案由任务，记录原文件 SHA256，不声称是本轮新请求。',
              '耗时按响应成功请求统计，另记录含重试总耗时；usage 不是账单费用。模型推理强度及图片处理差异保留在配置快照。',
              'GPT-6.1 Sol 待有效凭据补测；未以其它 GPT 替代。全量原八轨基准及开放题专业评分仍需继续完成。']
    if (BASE/'superseded.json').exists():
        lines[1:1] = ['', '**本协议已停止并被修订版替代。evidence 输入定义混淆了证据形式与法律相关性，不用于模型选型。原始请求、缺失项和未观测的在途请求保持记录。**', '']
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(str(target), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'run', 'report'])
    parser.add_argument('--split', choices=['development', 'holdout'], default='development')
    parser.add_argument('--models', default=','.join(ALIASES))
    parser.add_argument('--structured', action='store_true')
    parser.add_argument('--run-tag', default='', help='New run suffix after credential or protocol adaptation; original failures retained.')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 7))
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare': prepare()
    elif args.command == 'run': run(args)
    else: report(args.split, args.structured, args.run_tag)


if __name__ == '__main__': main()
