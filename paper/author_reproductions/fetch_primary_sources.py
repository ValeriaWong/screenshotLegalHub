"""Read primary pages for every registry entry; this never declares a method reproduced."""
import concurrent.futures
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import requests
import yaml
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'paper/author_reproductions/primary_sources/2026-10-29'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.title='';self.in_title=False
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.links += [v for k,v in attrs if k=='href' and v and ('github.com/' in v or 'huggingface.co/' in v)]
        if tag=='title':self.in_title=True
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
    def handle_data(self,data):
        if self.in_title:self.title+=data

def fetch(paper):
    result=dict(paper_id=paper['paper_id'],registered_reference=paper['reference'],pages=[])
    for number,url in enumerate(paper['sources']):
        page=dict(url=url)
        try:
            response=requests.get(url,timeout=(8,25),headers={'User-Agent':'ScreenshotLegal academic reproduction source audit/1.0'})
            body=response.text;filename=paper['paper_id']+'_'+str(number)+'.html'
            (OUT/filename).write_text(body,encoding='utf-8')
            parser=Links();parser.feed(body)
            page.update(status=response.status_code,final_url=response.url,title=parser.title,
                        repository_links=sorted(set(parser.links)),snapshot=filename,
                        sha256=hashlib.sha256(body.encode()).hexdigest())
        except requests.RequestException as error:page.update(status='unavailable',error=str(error))
        result['pages'].append(page)
    (OUT/(paper['paper_id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    papers=yaml.safe_load((ROOT/'paper_registry_v1.yaml').read_text(encoding='utf-8'))['papers']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(fetch,papers))
    (OUT/'index.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(registry_entries=len(results),pages=sum(len(r['pages']) for r in results),
                         available=sum(p.get('status')==200 for r in results for p in r['pages']))))
if __name__=='__main__':main()
