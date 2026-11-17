import hashlib,json,httpx
from html.parser import HTMLParser
from pathlib import Path
p=Path('paper/author_reproductions/jurisma');p.mkdir(exist_ok=True)
u='https://arxiv.org/html/2604.10470v1';r=httpx.get(u,follow_redirects=True,timeout=30);r.raise_for_status();(p/'paper_v1.html').write_bytes(r.content)
class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):
        if data.strip():self.parts.append(data.strip())
t=Text();t.feed(r.text);(p/'paper_v1.text.txt').write_text('\n'.join(t.parts),encoding='utf-8')
(p/'paper_source.json').write_text(json.dumps(dict(url=u,final_url=str(r.url),sha256=hashlib.sha256(r.content).hexdigest(),bytes=len(r.content)),indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(bytes=len(r.content),text_chars=sum(map(len,t.parts)),model_requests=0)))
