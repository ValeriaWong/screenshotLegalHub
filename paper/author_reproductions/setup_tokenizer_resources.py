"""Freeze official tiktoken resources used by the author environments; no inference."""
import argparse,hashlib,json,os,tempfile
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
EXPECTED={'cl100k_base':'223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7','o200k_base':'446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d','p50k_base':'94b5ca7dff4d00767bc256fdd1b27e5b17361d7b8a5f968547f9f23eb70d2069'}
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args();entries=[]
for name,expected in EXPECTED.items():
    url='https://openaipublic.blob.core.windows.net/encodings/'+name+'.tiktoken';key=hashlib.sha1(url.encode()).hexdigest()
    target=ROOT/'paper/.cache/tiktoken'/key
    if not target.exists():
        if args.check:raise FileNotFoundError(target)
        cache=Path(tempfile.gettempdir())/'data-gym-cache'/key
        data=cache.read_bytes() if cache.exists() else urlopen(url,timeout=60).read()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Official tokenizer SHA mismatch: '+name)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('Pinned tokenizer changed: '+name)
    entries.append(dict(name=name,url=url,path=target.relative_to(ROOT).as_posix(),sha256=expected))
(HERE/'tokenizer_resources.lock.json').write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(resources=len(entries),model_requests=0,cache_directory='paper/.cache/tiktoken')))
