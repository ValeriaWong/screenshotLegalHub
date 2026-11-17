"""One real screenshot exercises upload -> model extraction -> code retrieval -> export."""
from pathlib import Path
import base64
import json
import sys
import time
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub import benchmark as b

URL='http://127.0.0.1:18420'
CASE='软件闭环验收'


def main():
    output=ROOT/'reports/v1.0.0_evidence_workflow_acceptance.json'
    # This is a live acceptance run; preserve a successful previous run instead of rebilling it.
    completed = None
    if output.exists():
        old=b.read(output)
        if old.get('status')=='passed' and old.get('verified_run_id')==old.get('job_id'):print(json.dumps(old,ensure_ascii=True));return
        if old.get('status')=='passed':completed=old
    images=b.read(ROOT/'blocks/evidence/artifacts/demo_manifest.json')['images']
    image=next(x for x in images if x['image_id']=='5ad6f87311be1056f7197a9f_image_6.jpg')
    payload={'case_id':CASE,'extract':True,'files':[{'name':image['image_id'],'base64':base64.b64encode((ROOT/image['file']).read_bytes()).decode()}]}
    if completed:
        job=completed['job_id'];state={'status':'completed','result':completed['extraction_result']}
    else:
        response=requests.post(URL+'/api/import',json=payload,timeout=30);response.raise_for_status();job=response.json()['job_id']
        state={'status':'running','job_id':job,'case_id':CASE};b.write(output,state)
        for count in range(180):
            r=requests.get(URL+'/api/jobs',timeout=30);r.raise_for_status();state=r.json()[job]
            if count%10==0:print(json.dumps({'job':job,'status':state['status'],'completed':state['completed']},ensure_ascii=True),flush=True)
            if state['status']!='running':break
            time.sleep(2)
    if state['status'] not in ('completed','needs_review'):
        b.write(output,{'status':'failed','job_id':job,'job_status':state});raise RuntimeError('Workflow did not complete')
    response=requests.get(URL+'/api/search',params={'case_id':CASE,'q':'2000'},timeout=30);response.raise_for_status();result=response.json()
    assert result['model_requests']==0
    messages=[x for x in result['results'] if x['kind']=='message' and x['origin_type']=='fresh_model_extraction' and x.get('extraction_origin',{}).get('run_id')==job]
    assert messages and any('2000' in x['text'] for x in messages)
    source=messages[0]['source_refs'][0]
    assert source['bbox'] and source['evidence_page']==1
    response=requests.get(URL+'/api/image',params={'id':source['image_id']},timeout=30);response.raise_for_status()
    assert b.sha(ROOT/image['file'])==__import__('hashlib').sha256(response.content).hexdigest()
    response=requests.get(URL+'/api/export',params={'case_id':CASE,'q':'2000','format':'json'},timeout=30);response.raise_for_status()
    assert any(x['source_refs'] for x in response.json())
    passed={'status':'passed','job_id':job,'verified_run_id':job,'case_id':CASE,'extraction_result':state['result'],
            'retrieval_model_requests':0,'matching_message_ids':[x['id'] for x in messages], 'source_refs':source,
            'checks':['real upload','real configured vision-model request','validated message/event corpus',
                      'code retrieval with no model call','original image hash and source region','export citations'],
            'limitation':'Single development screenshot integration check, not a legal accuracy benchmark.'}
    b.write(output,passed);print(json.dumps(passed,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
