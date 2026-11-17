"""Download the official element example linked by the original model card."""
import hashlib,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
repository='PaddlePaddle/PaddleOCR-VL_demo';file='imgs/text_english_arabic.jpg'
metadata=requests.get('https://huggingface.co/api/datasets/'+repository,timeout=120);metadata.raise_for_status();revision=metadata.json()['sha']
url=f'https://huggingface.co/datasets/{repository}/resolve/{revision}/{file}'
response=requests.get(url,timeout=120);response.raise_for_status()
target=HERE/'native_inputs/text_english_arabic.jpg';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(response.content)
source=dict(repository=repository,revision=revision,file=file,url=url,sha256=hashlib.sha256(response.content).hexdigest(),model_card_reference='README.md element-level demonstration',full_benchmark=False)
(HERE/'native_inputs/source.json').write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(source))
