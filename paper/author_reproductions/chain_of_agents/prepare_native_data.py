"""Download original LongBench data ZIP at the verified public dataset revision; no models."""
import hashlib,json,requests,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
meta=json.loads((HERE/'native_inputs/longbench_hf_repository.json').read_text(encoding='utf-8'))
url='https://huggingface.co/datasets/'+meta['id']+'/resolve/'+meta['sha']+'/data.zip'
path=HERE/'native_inputs/longbench_data.zip'
if not path.exists():
 with requests.get(url,stream=True,timeout=(20,60)) as response:
  response.raise_for_status()
  with path.open('xb') as output:
   for chunk in response.iter_content(1024*1024):output.write(chunk)
with zipfile.ZipFile(path) as archive:
 name=next(n for n in archive.namelist() if n.endswith('/hotpotqa.jsonl') or n=='hotpotqa.jsonl')
 raw=archive.read(name)
 (HERE/'native_inputs/hotpotqa.jsonl').write_bytes(raw)
 row=json.loads(raw.splitlines()[0]);(HERE/'native_inputs/hotpotqa_first.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 provenance=dict(dataset=meta['id'],revision=meta['sha'],url=url,zip_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),member=name,member_sha256=hashlib.sha256(raw).hexdigest(),rows=len(raw.splitlines()),selected_index=0)
 (HERE/'native_inputs/dataset_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(status='downloaded',zip_bytes=path.stat().st_size,rows=provenance['rows'],context_chars=len(row['context']),question=row['input'])),flush=True)
