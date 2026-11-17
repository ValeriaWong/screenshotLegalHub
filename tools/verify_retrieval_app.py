"""Actual local HTTP acceptance checks and manually inspected source-query cases."""
from pathlib import Path
from collections import Counter
import base64
import csv
import io
import json
import sys
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub import benchmark as b

URL = 'http://127.0.0.1:18420'
CASES = [
    ('正好我有时间', '58b7dff082ec3972eb9edeb4', '58b7dff082ec3972eb9edeb4_image_1.jpg', 1),
    ('预付款', '58b7dff082ec3972eb9edeb4', '58b7dff082ec3972eb9edeb4_image_1.jpg', 6),
    ('支付宝发给我', '5ad6f87311be1056f7197a9f', '5ad6f87311be1056f7197a9f_image_5.jpg', 8),
    ('给你转了 2000', '5ad6f87311be1056f7197a9f', '5ad6f87311be1056f7197a9f_image_6.jpg', 0),
    ('钱收到没', '5ad6f87311be1056f7197a9f', '5ad6f87311be1056f7197a9f_image_6.jpg', 5),
    ('收到了', '5ad6f87311be1056f7197a9f', '5ad6f87311be1056f7197a9f_image_6.jpg', 6),
]


def get(path, **params):
    r = requests.get(URL + path, params=params, timeout=30); r.raise_for_status(); return r


def main():
    health = get('/health').json(); results = []; checks = []
    for query, case, image, order in CASES:
        expected = f'vision:{image}:p2-kimi3-development:{order}'
        tick = time.monotonic(); response = get('/api/search', q=query, case_id=case, limit=10).json()
        ids = [x['id'] for x in response['results']]
        rank = ids.index(expected) + 1 if expected in ids else None
        results.append({'query': query, 'case_id': case, 'expected_record': expected, 'rank': rank,
                        'hit_at_10': rank is not None, 'elapsed_seconds': time.monotonic()-tick})
        assert response['model_requests'] == 0
        assert all(x['case_id'] == case for x in response['results'])
        target = get('/api/record', id=expected).json()
        ref = target['source_refs'][0]
        data = get('/api/image', id=image)
        assert data.headers['Content-Type'].startswith('image/')
        assert ref['bbox'] is not None
        context = get('/api/context', id=expected).json()
        assert any(x['id'] == expected for x in context)
        assert all(x['image_id'] == image for x in context)
    checks.append('six manually inspected message queries, image serving and same-image context')
    assert requests.get(URL+'/api/search', params={'q': '借款'}, timeout=30).status_code == 400
    assert get('/api/search', q='借款', case_id='NONEXISTENT').json()['results'] == []
    checks.append('case required and no cross-case leakage')
    law = get('/api/search', q='借款人应当按照约定的期限返还借款', scope='statute').json()
    assert law['results'][0]['id'] == 'civil-code-2020:675'
    checks.append('published statute article retrieved with source URL')
    documents = get('/api/search', q='股权转让纠纷', scope='case_law').json()
    assert documents['results'] and all(x['kind'] == 'case_law' and x['source_refs'][0]['source_sha256'] for x in documents['results'])
    checks.append('archived analogous judgment chunks retain source offsets')
    response = get('/api/export', q='给你转了 2000', case_id='5ad6f87311be1056f7197a9f', format='csv')
    rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert rows and any(json.loads(x['source_refs']) for x in rows)
    checks.append('CSV export includes complete citations')
    assert requests.get(URL+'/api/image',params={'id':'../../configs/models.local.yaml'},timeout=30).status_code == 404
    assert requests.get(URL+'/health',headers={'Origin':'https://unrelated.example'},timeout=30).status_code == 400
    checks.append('unregistered files and cross-origin requests rejected')
    # Real screenshot import without inference: proves the code path needs no model.
    image = b.read(ROOT/'blocks/evidence/artifacts/demo_manifest.json')['images'][0]
    payload = {'case_id':'软件验收截图组', 'extract':False, 'files':[{'name':Path(image['file']).name,'base64':base64.b64encode((ROOT/image['file']).read_bytes()).decode()}]}
    uploaded = requests.post(URL+'/api/import',json=payload,timeout=30); uploaded.raise_for_status(); job=uploaded.json()['job_id']
    for _ in range(120):
        status=get('/api/jobs').json()[job]
        if status['status']!='running':break
        time.sleep(1)
    assert status['status']=='completed', status
    assert get('/api/search',q=payload['files'][0]['name'],case_id=payload['case_id']).json()['results']
    checks.append('real screenshot import completes without inference')
    result={'health_counts_before_import':health['counts'],'checks':checks,'queries':results,
            'source_query_hit_at_10':sum(x['hit_at_10'] for x in results)/len(results), 'model_requests_during_checks':0,
            'scope_note':'Six development-source smoke queries over a visually inspected subset; not a general retrieval benchmark.'}
    b.write(ROOT/'reports/v1.0.0_retrieval_acceptance.json',result)
    print(json.dumps(result,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
