"""Verify the running one-case HTTP flow without sending additional model requests."""
import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub import benchmark as b

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:18420');parser.add_argument('--report',default='reports/v1.0.0_one_case_acceptance.json');args=parser.parse_args()
    def get(route,**params):
        r=requests.get(args.url+route,params=params,timeout=10);r.raise_for_status();return r
    responses=list((b.ROOT/'blocks/evidence/artifacts/casework/runs').glob('*/response.json'))
    before={p:b.sha(p) for p in responses}
    state=get('/api/case/current').json();active=state['analysis'];assert active
    assert active['request_proof']['http_status']==200 and active['request_proof']['response_id']
    assert state['message_count']==61 and len(state['images'])==6
    image_count=0
    for image in state['images']:
        blob=get('/api/case/image',id=image['image_id']).content
        assert hashlib.sha256(blob).hexdigest()==image['sha256'];image_count+=1
        versioned=get('/api/case/image',id=image['image_id'],sha=image['sha256'])
        assert versioned.content==blob and 'private' in versioned.headers['Cache-Control']
        wrong=requests.get(args.url+'/api/case/image',params={'id':image['image_id'],'sha':'wrong-version'},timeout=10)
        assert wrong.status_code==400
    msgs={m['id']:m for m in state['messages']};quote_count=0
    for record in active['facts']+active['meanings']:
        resolved=get('/api/case/record',id=record['id']).json();assert resolved['id']==record['id']
        for ref in record['source_refs']:
            assert ref['quote'] in msgs[ref['message_id']]['text']
            assert ref['bbox']==next(r['bbox'] for r in msgs[ref['message_id']]['source_refs'] if r['image_id']==ref['image_id'])
            context=get('/api/case/context',id=ref['message_id']).json()
            assert any(m['id']==ref['message_id'] for m in context);quote_count+=1
    backend=[];wall=[];queries=['收款确认','要约','承诺','2000','不够','你选吧','']
    for _ in range(4):
        for query in queries:
            tick=time.perf_counter();result=get('/api/case/search',q=query,kind='all').json()
            wall.append((time.perf_counter()-tick)*1000);backend.append(result['elapsed_ms'])
            assert all(r['case_id']==state['case_id'] for r in result['results'])
    receipt=get('/api/case/search',q='收款确认',kind='all').json()
    assert any(r.get('event_type')=='receipt_confirmation' for r in receipt['results'])
    for kind,count in [('facts',4),('meanings',6),('message',61)]:
        rows=get('/api/case/search',q='',kind=kind).json()['results'];assert len(rows)==count,(kind,len(rows))
    exported=get('/api/case/export').json();assert exported['run_id']==active['run_id']
    assert len(exported['presentation_timeline']['pages'])==len(state['images'])
    assert exported['presentation_timeline']['model_requests']==0
    graph=exported['presentation_timeline']
    assert len(graph['legal_events'])==8 and len(graph['contract_terms'])==8
    assert len(graph['conversations'])==1 and len(graph['conversations'][0]['image_ids'])==6
    english=get('/api/case/search',q='receipt confirmation',kind='all').json()
    assert english['query']=='receipt confirmation' and english['normalized_query']=='收款确认'
    assert {r['id'] for r in english['results']}=={r['id'] for r in receipt['results']}
    after={p:b.sha(p) for p in (b.ROOT/'blocks/evidence/artifacts/casework/runs').glob('*/response.json')}
    assert before==after,'Viewing and searching caused model requests'
    def pct(values,p):return round(sorted(values)[min(len(values)-1,int(len(values)*p))],2)
    result={'url':args.url,'checked_at':time.strftime('%Y-%m-%d %H:%M:%S'),'case_id':state['case_id'],'run_id':active['run_id'],
            'real_response':active['request_proof'],'images_hash_verified':image_count,'quotes_resolved':quote_count,
            'facts':len(active['facts']),'meanings':len(active['meanings']),'messages':state['message_count'],
            'search_samples':len(backend),'backend_ms':{'p50':round(statistics.median(backend),2),'p95':pct(backend,.95),'max':round(max(backend),2)},
            'http_ms':{'p50':round(statistics.median(wall),2),'p95':pct(wall,.95),'max':round(max(wall),2)},
            'retrieval_new_model_responses':0,'export_matches_active':True,'review_status':active.get('review',{}).get('status'),
            'named_conversations':len(graph['conversations']),'legal_nodes':len(graph['legal_events']),'contract_terms':len(graph['contract_terms']),'english_alias_preserves_matches':True}
    b.write(b.ROOT/args.report,result)
    print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
