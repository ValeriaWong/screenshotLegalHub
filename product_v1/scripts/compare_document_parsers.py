"""Same synthetic Office bytes, independent parse runs and recorded native artifacts."""
import json,time,hashlib
from pathlib import Path
from types import SimpleNamespace
from tempfile import mkdtemp
from screenshotlegal.settings import ROOT
from screenshotlegal.documents.service import Documents
from screenshotlegal.documents.parsers import capabilities

def main():
    root=ROOT/'reports/evidence-upgrade-2026-10-28'
    fixtures=next((root/'parser').glob('run-*/fixtures'))
    run=Path(mkdtemp(prefix='compare-',dir=root))
    service=Documents(SimpleNamespace(settings=SimpleNamespace(data_dir=run/'data',max_upload_bytes=20*1024*1024)))
    rows=[]
    for name in ['notes.docx','table.xlsx','slides.pptx','data.csv']:
        data=(fixtures/name).read_bytes()
        ids=[]
        for engine in ['mineru','docling']:
            started=time.monotonic()
            doc=service.ingest('synthetic',name,data,{'parser':engine})
            ids.append(doc['id'])
            doc=service.parse_next('synthetic',doc['id'],3)
            blocks=service.store.blocks(doc['id'])
            assert doc['status']=='complete'
            assert any('520' in b['text'] for b in blocks),(name,engine)
            rows.append(dict(filename=name,source_sha256=hashlib.sha256(data).hexdigest(),engine=engine,
                parse_run_id=doc['id'],profile_digest=doc['profile_digest'],elapsed_ms=round((time.monotonic()-started)*1000),
                blocks=len(blocks),characters=sum(len(b['text']) for b in blocks),producer=doc.get('producer'),artifacts=doc.get('artifacts',[]),
                snapshot_id=service.store.freeze('synthetic',doc['id'])['id'],checks={'known_amount_520':True,'complete':True}))
        assert ids[0]!=ids[1]
    report=dict(status='PASS',scope='synthetic native Office engineering smoke; not legal accuracy',capabilities=capabilities(),results=rows)
    (run/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','report':str(run/'results.json')}))
if __name__=='__main__':main()
