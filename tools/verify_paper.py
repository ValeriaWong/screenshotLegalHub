"""Render every manuscript page and check citations/overflow without editing sources."""
from pathlib import Path
import hashlib,json,re
import pdfplumber
ROOT=Path(__file__).resolve().parents[1]
PDF=ROOT/'output/pdf/screenshotlegalbench_working_draft.pdf'

def main():
    dest=ROOT/'tmp/paper/rendered';dest.mkdir(parents=True,exist_ok=True)
    pages=[]
    with pdfplumber.open(PDF) as doc:
        for i,page in enumerate(doc.pages):
            path=dest/f'page-{i+1:02d}.png'
            page.to_image(resolution=110).save(path)
            words=page.extract_words()
            # ACL review line numbers occupy the outer margin; only page-bound checks here.
            escaped=[w['text'] for w in words if w['x0']<0 or w['x1']>page.width+1 or w['top']<0 or w['bottom']>page.height+1]
            pages.append({'page':i+1,'image':str(path.relative_to(ROOT)),'words':len(words),'outside_page':escaped})
    log=(ROOT/'tmp/paper/build/main.log').read_text(encoding='utf-8',errors='replace')
    findings={
        'pdf':str(PDF.relative_to(ROOT)),'sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),'pages':pages,
        'overfull_boxes':re.findall(r'Overfull[^\n]+',log),
        'undefined_references':re.findall(r'[^\n]*(?:undefined|multiply defined)[^\n]*',log,re.I),
        'visual_review':'pending human/model page inspection; rendering alone is not a layout acceptance',
    }
    out=ROOT/'reports/research/paper_verification.json'
    out.write_text(json.dumps(findings,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pages':len(pages),'overfull_boxes':findings['overfull_boxes'],'undefined_references':findings['undefined_references'],'outside_page':[p for p in pages if p['outside_page']]},ensure_ascii=True))
    if findings['overfull_boxes'] or findings['undefined_references'] or any(p['outside_page'] for p in pages):raise SystemExit(1)

if __name__=='__main__':main()
