"""Pin official PaddleOCR-VL v1 resources; downloading never executes remote code."""
import argparse,hashlib,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[3]
TARGET=ROOT/'paper/.models/paddleocr_vl'
LOCK=Path(__file__).with_name('model.lock.json')
MODEL='PaddlePaddle/PaddleOCR-VL'
p=argparse.ArgumentParser();p.add_argument('--weights',action='store_true');args=p.parse_args()
if LOCK.exists():
    lock=json.loads(LOCK.read_text(encoding='utf-8'));revision=lock['revision']
    data=requests.get(f'https://huggingface.co/api/models/{MODEL}/revision/{revision}',timeout=120).json()
else:
    data=requests.get(f'https://huggingface.co/api/models/{MODEL}',timeout=120).json()
    revision=data['sha'];lock=dict(model=MODEL,revision=revision,files={})
files=[v['rfilename'] for v in data['siblings'] if not v['rfilename'].startswith('.')]
for name in files:
    weight=name.endswith('.safetensors') and '/' not in name
    if not (name.endswith(('.py','.json','.md','.jinja','.txt','.model')) or (args.weights and weight)):continue
    if name in lock['files']:
        path=TARGET/name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==lock['files'][name]['sha256']:continue
    path=TARGET/name;path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.partial');offset=tmp.stat().st_size if tmp.exists() else 0
    r=requests.get(f'https://huggingface.co/{MODEL}/resolve/{revision}/{name}',headers={'Range':f'bytes={offset}-'} if offset else {},timeout=300,stream=True);r.raise_for_status()
    if offset and r.status_code==206:
        if not r.headers.get('Content-Range','').startswith(f'bytes {offset}-'):raise ValueError('Invalid download resume range')
    else:offset=0
    size=offset;last=size//(100*1024*1024)
    with tmp.open('ab' if offset else 'wb') as out:
        for chunk in r.iter_content(1024*1024):
            if chunk:
                out.write(chunk);size+=len(chunk)
                if size//(100*1024*1024)>last:
                    last=size//(100*1024*1024);print(json.dumps(dict(file=name,downloaded_bytes=size)),flush=True)
    h=hashlib.sha256()
    with tmp.open('rb') as content:
        for chunk in iter(lambda:content.read(1024*1024),b''):h.update(chunk)
    metadata=requests.get(f'https://huggingface.co/api/models/{MODEL}/revision/{revision}',params={'blobs':'true'},timeout=120);metadata.raise_for_status()
    sibling=next(v for v in metadata.json()['siblings'] if v['rfilename']==name)
    expected=sibling.get('lfs',{}).get('sha256')
    if expected and h.hexdigest()!=expected:raise ValueError('Original model SHA256 mismatch')
    tmp.replace(path);lock['files'][name]=dict(sha256=h.hexdigest(),bytes=size,expected_lfs_sha256=expected)
    LOCK.write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(file=name,bytes=size,revision=revision)),flush=True)
print(json.dumps(dict(model=MODEL,revision=revision,total_files=len(files),selected=list(lock['files']))))
