"""Reproducible native-parser smoke using synthetic material, never live case data."""
import argparse
import json
import subprocess
from pathlib import Path
from tempfile import mkdtemp
from types import SimpleNamespace
from screenshotlegal.documents.service import Documents
from screenshotlegal.documents.adapter import MinerUAdapter
from screenshotlegal.settings import ROOT

def main():
    args=argparse.ArgumentParser()
    args.add_argument('--output',type=Path,default=ROOT/'reports/document-parser-local')
    output=args.parse_args().output.resolve();output.mkdir(parents=True,exist_ok=True)
    run=Path(mkdtemp(prefix='run-',dir=output))
    fixtures=run/'fixtures'
    adapter=MinerUAdapter()
    subprocess.run([str(adapter.python),str(ROOT/'scripts/make-document-fixtures.py'),str(fixtures)],check=True)
    service=Documents(SimpleNamespace(settings=SimpleNamespace(data_dir=run/'data',max_upload_bytes=20*1024*1024)),adapter)
    report=[]
    for name in ['paper.pdf','notes.docx','table.xlsx','slides.pptx','data.csv']:
        row=service.ingest('synthetic',name,(fixtures/name).read_bytes());steps=[]
        while row['status']!='complete':
            row=service.parse_next('synthetic',row['id'],3)
            steps.append(dict(status=row['status'],parsed_pages=row['parsed_pages'],blocks=row['blocks']))
        result=service.read('synthetic',row['id'])
        assert any('520' in block['text'] for block in result['items']),name
        if name=='paper.pdf':
            assert [step['parsed_pages'] for step in steps]==[3,6,7]
            assert {b['page'] for b in result['items']}==set(range(1,8))
            preview,_=service.preview('synthetic',row['id'],7)
            (run/'page7.png').write_bytes(preview.read_bytes())
        report.append(dict(filename=name,steps=steps,first_blocks=result['items'][:2]))
    (run/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status='PASS',report=str(run/'results.json')),ensure_ascii=False))
if __name__=='__main__': main()
