import httpx,json,hashlib
from pathlib import Path
from html.parser import HTMLParser
p=Path(r'D:/workspace/screenshotLegalHub/paper/author_reproductions/jurisma/native_inputs')
class Text(HTMLParser):
 def __init__(self):super().__init__();self.p=[];self.current=None
 def handle_starttag(self,t,a):
  if t=='p':self.current=[]
 def handle_data(self,s):
  if self.current is not None:self.current.append(s)
 def handle_endtag(self,t):
  if t=='p' and self.current is not None:self.p.append(''.join(self.current).strip());self.current=None
urls={'amendment_viii':'https://www.gjxfj.gov.cn/gjxfj/fgwj/flfg/webinfo/2014/05/1601761496857362.htm','criminal_1997':'https://www.spp.gov.cn/spp/fl/201802/t20180206_364975.shtml'}
for name,url in urls.items():
 r=httpx.get(url,timeout=40,follow_redirects=True);r.raise_for_status();(p/(name+'.html')).write_bytes(r.content); t=Text();t.feed(r.content.decode('utf-8'));(p/(name+'.paragraphs.json')).write_text(json.dumps(t.p,ensure_ascii=False,indent=2),encoding='utf-8');print(name,len(r.content),json.dumps([dict(index=i,text=s) for i,s in enumerate(t.p) if s.startswith(('二十二、','二十三、','第五十条','第十二条','第十三条')) or '2011年5月1日' in s],ensure_ascii=False))
