"""Fetch fixed original LegalBench files and verify their exact Git blob identities.
No model request. Existing differing files are preserved. Uses the project's HTTP
client/proxy configuration, not a replacement dataset or latest unpinned URL.
"""
import hashlib,json,sys
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
items=json.loads((HERE/'expected_source_blobs.json').read_text(encoding='utf-8'));done=[]
with httpx.Client(follow_redirects=True,timeout=30) as client:
    for item in items:
        url='https://huggingface.co/datasets/nguha/legalbench/resolve/daec8237410aa23e3faf4bc41ad8b3a7e1696826/'+item['path']
        reply=client.get(url);reply.raise_for_status();data=reply.content
        assert len(data)==item['size'] and hashlib.sha1(('blob '+str(len(data))+'\0').encode()+data).hexdigest()==item['blob']
        destination=ROOT/'paper/upstream_sources/legalbench_data'/item['path']
        if destination.exists() and destination.read_bytes()!=data:raise ValueError('Existing differing source preserved: '+item['path'])
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
        done.append(dict(**item,url=url,sha256=hashlib.sha256(data).hexdigest(),git_blob_verified=True))
        (HERE/'source_downloads_verified.json').write_text(json.dumps(dict(commit='daec8237410aa23e3faf4bc41ad8b3a7e1696826',model_requests=0,files=done),indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(path=item['path'],bytes=len(data),git_blob_verified=True)),flush=True)
