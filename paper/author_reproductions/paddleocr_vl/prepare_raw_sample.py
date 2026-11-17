"""Freeze the raw document page used by the official v1 pipeline example; no output panel."""
import hashlib,json
from pathlib import Path
import requests
HERE=Path(__file__).resolve().parent
url='https://paddle-model-ecology.bj.bcebos.com/paddlex/imgs/demo_image/paddleocr_vl_demo.png'
r=requests.get(url,timeout=120);r.raise_for_status()
p=HERE/'native_inputs/paddleocr_vl_demo.png';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.content)
s=dict(url=url,sha256=hashlib.sha256(r.content).hexdigest(),reference='Pinned original model card v1 pipeline raw input',contains_reference_output=False,full_benchmark=False)
(p.with_suffix('.source.json')).write_text(json.dumps(s,indent=2)+'\n',encoding='utf-8');print(json.dumps(s))
