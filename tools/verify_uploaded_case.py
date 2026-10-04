"""Verify the actual uploaded case and source isolation without calling models."""
import hashlib
import json
import sys
from pathlib import Path
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub import benchmark as b

def main():
    cid=b.read(b.ROOT/'reports/v1.1.0_uploaded_test_case.json')['case_id']
    s=requests.Session();s.trust_env=False;base='http://127.0.0.1:18420'
    def get(path,**params):
        r=s.get(base+path,params={'case_id':cid,**params},timeout=10);r.raise_for_status();return r
    state=get('/api/case/current').json();g=get('/api/case/timeline').json();a=state['analysis']
    assert a and state['job']['status']=='completed' and state['job']['vision_complete']
    assert a['request_proof']['http_status']==200 and a['request_proof']['response_id']
    hashes=0;quotes=0
    for image in state['images']:
        blob=get('/api/case/image',id=image['image_id'],sha=image['sha256']).content
        assert hashlib.sha256(blob).hexdigest()==image['sha256'];hashes+=1
    messages={m['id']:m for m in state['messages']}
    assert {m['image_id'] for m in messages.values()}=={i['image_id'] for i in state['images']}
    for record in a['facts']+a['meanings']+g['legal_events']+g['contract_terms']:
        for ref in record['source_refs']:
            m=messages[ref['message_id']];assert ref['quote'] in m['text'] and m['case_id']==cid;quotes+=1
    foreign=s.get(base+'/api/case/image',params={'case_id':cid,'id':'5ad6f87311be1056f7197a9f_image_5.jpg'},timeout=10)
    assert foreign.status_code==404
    exported=get('/api/case/export').json();assert exported['case_id']==cid
    assert len(exported['images'])==len(state['images']) and len(exported['messages'])==state['message_count']
    result={'case_id':cid,'actual_run':a['run_id'],'actual_response':a['request_proof'],'source_hashes_checked':hashes,'quotes_checked':quotes,
        'image_coverage':state['quality'],'facts':len(a['facts']),'meanings':len(a['meanings']),'legal_nodes':len(g['legal_events']),
        'terms':len(g['contract_terms']),'cross_case_image_rejected':True,'export_case_matches':True,'validation_model_requests':0}
    b.write(b.ROOT/'reports/v1.1.0_upload_acceptance.json',result);print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
