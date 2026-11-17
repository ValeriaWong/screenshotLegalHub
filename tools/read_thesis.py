"""Extract thesis text for asset reconciliation; preserve original files."""
from pathlib import Path
import json
import pdfplumber
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'reports/restart/thesis_text';out.mkdir(parents=True,exist_ok=True)
source=ROOT.parent.parent/'\u6bd5\u4e1a\u6587\u6863'
records=[]
for p in source.glob('*.pdf'):
    if not any(k in p.name.lower() for k in ['202230311326_','dataset_final','json']):continue
    try:
        with pdfplumber.open(p) as doc:
            texts=[f'\n--- PAGE {i+1} ---\n'+(page.extract_text() or '') for i,page in enumerate(doc.pages)]
        (out/(p.stem+'.txt')).write_text('\n'.join(texts),encoding='utf-8')
        records.append({'source':str(p),'pages':len(texts),'text_file':str((out/(p.stem+'.txt')).relative_to(ROOT))})
    except Exception as e:records.append({'source':str(p),'error':str(e)})
(out/'index.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(records,ensure_ascii=False))
