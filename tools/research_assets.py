"""Extract authorized research assets; source ZIP/PDF/XLSX files stay read-only."""
from pathlib import Path
import hashlib, io, json, re, zipfile
import pdfplumber
import openpyxl
from tools.restart_inventory import zip_name

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/research'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records=[]
    with zipfile.ZipFile(ROOT/'归档.zip') as archive:
        for entry in archive.infolist():
            name=zip_name(entry)
            if entry.is_dir() or name.startswith('__MACOSX/'): continue
            if not name.endswith(('.pdf','.xlsx')): continue
            raw=archive.read(entry)
            item={'source':'归档.zip::'+name,'sha256':hashlib.sha256(raw).hexdigest()}
            if name.endswith('.pdf'):
                with pdfplumber.open(io.BytesIO(raw)) as doc:
                    pages=[page.extract_text() or '' for page in doc.pages]
                dest=OUT/'archive_pdf_text'/Path(name).with_suffix('.txt')
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text('\n'.join(f'--- PAGE {i+1} ---\n{t}' for i,t in enumerate(pages)),encoding='utf-8')
                item.update(pages=len(pages),text_path=str(dest.relative_to(ROOT)),keyword_pages=[])
                for i,t in enumerate(pages):
                    hits=re.findall(r'rebuttal|reviewer|official review|审稿|评审|GPT.?4o?|Claude|ScreenshotLegalBench',t,re.I)
                    if hits:item['keyword_pages'].append({'page':i+1,'keywords':sorted(set(hits))})
            elif '错误' in name:
                wb=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=False)
                item['sheets']=[]
                for sheet in wb:
                    sheet.reset_dimensions()
                    rows=[[str(v) if v is not None else None for v in row] for row in sheet.iter_rows(values_only=True)]
                    item['sheets'].append({'name':sheet.title,'rows':rows})
                wb.close()
                (OUT/'historical_error_rows.json').write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
            records.append(item)
    # Do not process unrelated student administration or personal documents.
    for p in (ROOT.parent.parent/'毕业文档').glob('*.pdf'):
        if 'emnlp' not in p.name.lower(): continue
        with pdfplumber.open(p) as doc:
            first=doc.pages[0].extract_text() or ''
        records.append({'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'first_page':first})
    (OUT/'research_assets.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'source':r['source'],'pages':r.get('pages'),'keyword_pages':len(r.get('keyword_pages',[]))} for r in records],ensure_ascii=True))

if __name__=='__main__':main()
