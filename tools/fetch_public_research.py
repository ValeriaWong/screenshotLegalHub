"""Download only public research PDFs explicitly located during asset discovery."""
from pathlib import Path
import hashlib, json
import requests
import pdfplumber
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/research'

def main():
    inventory=json.loads((OUT/'github_research_inventory.json').read_text(encoding='utf-8'))
    assets=[]
    for entry in inventory['trees']['bench-tree']['tree']:
        if entry['path'].endswith('.pdf'):
            assets.append(('https://raw.githubusercontent.com/ValeriaWong/ScreenshotLegalBench/'+inventory['trees']['bench-tree']['sha']+'/'+entry['path'],Path(entry['path']).name))
    assets.append(('https://openreview.net/pdf?id=MMrA9opOh5','ScreenshotLegalBench_openreview.pdf'))
    results=[]
    for url,name in assets:
        item={'url':url,'name':name}
        try:
            response=requests.get(url,timeout=30)
            response.raise_for_status()
            if not response.content.startswith(b'%PDF-'):raise ValueError('Server did not return a PDF; authentication or browser check may be required')
            dest=OUT/'sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(response.content)
            item.update(path=str(dest.relative_to(ROOT)),sha256=hashlib.sha256(response.content).hexdigest())
            with pdfplumber.open(dest) as doc:
                pages=[p.extract_text() or '' for p in doc.pages]
            text_dest=OUT/'public_pdf_text'/Path(name).with_suffix('.txt')
            text_dest.parent.mkdir(parents=True,exist_ok=True)
            text_dest.write_text('\n'.join(f'--- PAGE {i+1} ---\n{t}' for i,t in enumerate(pages)),encoding='utf-8')
            item.update(pages=len(pages),text_path=str(text_dest.relative_to(ROOT)))
        except Exception as e:item['error']=str(e)[:180]
        results.append(item)
        print(json.dumps(item,ensure_ascii=True),flush=True)
    (OUT/'public_downloads.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
