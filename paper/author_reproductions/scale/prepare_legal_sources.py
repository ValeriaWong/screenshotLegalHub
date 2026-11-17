"""Extract selected, independently published legal text for SCALE; no model calls.
Downloaded government/court snapshots are retained. Expert review remains unreviewed.
"""
import hashlib,json,sys
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'product_v1/backend/src'))
import yaml
class Paragraphs(HTMLParser):
    def __init__(self):super().__init__();self.result=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='p':self.current=[]
    def handle_data(self,data):
        if self.current is not None:self.current.append(data)
    def handle_endtag(self,tag):
        if tag=='p' and self.current is not None:self.result.append(''.join(self.current).strip());self.current=None
folder=Path(__file__).parent/'native_inputs'
def extract(name,start,end):
    raw=(folder/(name+'.html')).read_bytes();p=Paragraphs();p.feed(raw.decode('utf-8'))
    indices=[i for i,s in enumerate(p.result) if s.startswith(start)]
    if len(indices)!=1:raise ValueError('Ambiguous article boundary: '+start)
    first=indices[0];last=next(i for i in range(first+1,len(p.result)) if p.result[i].startswith(end))
    return '\n'.join(p.result[first:last]),hashlib.sha256(raw).hexdigest()
config=[('civil-code-675','civil-code','第六百七十五条','第六百七十六条','https://www.cac.gov.cn/2020-06/01/c_15925617772683192.htm'),
        ('civil-code-679','civil-code','第六百七十九条','第六百八十条','https://www.cac.gov.cn/2020-06/01/c_15925617772683192.htm'),
        ('lending-9','lending','第九条','第十条','https://www.sdcourt.gov.cn/bzbxfy/374836/374849/6811951/index.html')]
assert '2020年12月23日' in (folder/'lending.html').read_text(encoding='utf-8')
pack=ROOT/'product_v1/matterpacks/cn/civil/private_lending/1.0.0/authorities.yaml'
rows=yaml.safe_load(pack.read_text(encoding='utf-8'));provenance=[]
for sid,name,start,end,url in config:
    text,sha=extract(name,start,end);row=next(r for r in rows if r['id']==sid)
    row.update(text=text,source_url=url,source_digest=hashlib.sha256(text.encode()).hexdigest())
    if row['verification_status']!='unverified':raise ValueError('Do not change existing reviewed authority')
    provenance.append(dict(id=sid,source_url=url,raw_snapshot='paper/author_reproductions/scale/native_inputs/'+name+'.html',
        snapshot_sha256=sha,text_sha256=row['source_digest'],article_start=start,article_end_exclusive=end,
        extraction='HTML p text in exact article boundaries; trim paragraph edge whitespace; join paragraphs by newline',
        expert_review_status='unreviewed',snapshot_saved_at=datetime.fromtimestamp((folder/(name+'.html')).stat().st_mtime,timezone.utc).isoformat()))
pack.write_text(yaml.safe_dump(rows,allow_unicode=True,sort_keys=False,width=120),encoding='utf-8')
(folder/'legal_sources.json').write_text(json.dumps(dict(authorities=rows,provenance=provenance),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(authorities=len(rows),characters=[len(r['text']) for r in rows],supplier_requests=0,expert_review_status='unreviewed')))
