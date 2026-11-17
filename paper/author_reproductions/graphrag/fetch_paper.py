import httpx,hashlib,json
from pathlib import Path
p=Path(r'D:/workspace/screenshotLegalHub/paper/author_reproductions/graphrag');url='https://arxiv.org/html/2404.16130v1';r=httpx.get(url,timeout=40,follow_redirects=True);r.raise_for_status();(p/'paper_v1.html').write_bytes(r.content);(p/'paper_source.json').write_text(json.dumps(dict(url=url,final_url=str(r.url),sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content)),indent=2)+'\n',encoding='utf-8');print(len(r.content))
