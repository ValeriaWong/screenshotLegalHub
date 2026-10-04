"""Read-only acceptance of actual review evidence; never records a user decision."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import statistics
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18420)
    args = parser.parse_args()
    base = f'http://127.0.0.1:{args.port}'
    session = requests.Session()
    session.trust_env = False

    def get(path, **params):
        response = session.get(base + path, params=params, timeout=30)
        response.raise_for_status()
        return response

    begin = time.perf_counter()
    queue = get('/api/review/queue', status='all', limit=200).json()
    first = (time.perf_counter() - begin) * 1000
    assert queue['total'] == 48 and len(queue['cases']) == 2
    assert queue['counts']['pending'] == 48, 'Formal database must contain no test decisions'
    assert all(x['review']['reviewer'] == '' for x in queue['items'])
    catalog = get('/api/workspace/cases').json()['cases']
    ids = {x['case_id'] for x in queue['cases']}
    assert len(catalog) >= 315 and all(x['status'] == 'analyzed' for x in queue['cases'])
    refs = [(i['case_id'], r) for i in queue['items'] for r in i['source_refs']]
    unique_records = {(cid, r['message_id']) for cid, r in refs}
    with ThreadPoolExecutor(max_workers=6) as pool:
        values = list(pool.map(lambda key: (key, get('/api/case/record', case_id=key[0], id=key[1]).json()), sorted(unique_records)))
    records = dict(values)
    for cid, ref in refs:
        row = records[(cid, ref['message_id'])]
        assert row['case_id'] == cid and ref['quote'] in row['text']
        assert any(s['image_id'] == ref['image_id'] and s['bbox'] == ref['bbox'] for s in row['source_refs'])
    images = {(item['case_id'], s['image_id']): s for item in queue['items'] for s in item['sources']}
    for (cid, iid), source in images.items():
        image = get('/api/case/image', case_id=cid, id=iid, sha=source['sha256'])
        assert hashlib.sha256(image.content).hexdigest() == source['sha256']
    for cid in sorted(ids):
        export = get('/api/review/export', case_id=cid).json()
        assert export['case_id'] == cid and export['items']
        assert all(i['reviewed_text'] is None for i in export['items'])
    foreign = next(i for i in queue['items'] if i['kind'] == 'qa_claim')
    other_case = next(cid for cid in ids if cid != foreign['case_id'])
    assert session.get(base + '/api/review/item', params={'case_id': other_case, 'item_id': foreign['id']}, timeout=20).status_code == 404
    assert session.get(base + '/api/review/queue?kind=invalid', timeout=20).status_code == 400
    assert session.get(base + '/api/review/queue', headers={'Origin': 'https://outside.invalid'}, timeout=20).status_code == 400
    assert session.post(base + '/api/review/decision', json={'case_id': foreign['case_id'], 'item_id': foreign['id'], 'decision': 'confirmed'}, timeout=20).status_code == 400
    timings = []
    for _ in range(20):
        begin = time.perf_counter()
        get('/api/review/queue', limit=30)
        timings.append((time.perf_counter() - begin) * 1000)
    final = get('/api/review/queue', limit=1).json()
    assert final['counts']['pending'] == 48
    result = {
        'server': base, 'registered_cases': len(catalog), 'analyzed_cases_in_default_review': len(queue['cases']),
        'review_items': queue['total'], 'kinds': dict(Counter(i['kind'] for i in queue['items'])),
        'formal_pending_items': final['counts']['pending'], 'formal_user_decisions_created_by_test': 0,
        'source_refs_verified_against_transcripts_and_pixel_boxes': len(refs),
        'unique_message_records_verified': len(unique_records), 'original_image_sha256_checks': len(images),
        'cross_case_reference_rejected': True, 'invalid_requests_and_cross_origin_rejected': True,
        'unreviewed_items_not_exported_as_reviewed_text': True, 'model_requests_made_by_test': 0,
        'queue_http_ms': {'first_request': round(first, 2), 'warm_samples': 20,
                          'median': round(statistics.median(timings), 2),
                          'p95': round(sorted(timings)[18], 2), 'max': round(max(timings), 2)},
    }
    (ROOT / 'reports/v1.2.0_review_http.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
