"""Pin reviewed author entrypoints and native resources; does not execute model code."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];lockpath=Path(__file__).with_name('sources.lock.json');lock=json.loads(lockpath.read_text(encoding='utf-8'))
for name,url,paper,patterns in [
 ('lawflow','https://github.com/minnesotanlp/LawFlow','L03',['README*','modeling/*.ipynb','data_analysis/*.py']),
 ('scale','https://github.com/khatrimann/SCALE','L09',['*.py','Guides/JSON/*.json','Hierarchies/Iter/*.txt','cases/cases_new_hudoc_001-231088.csv'])]:
    folder=ROOT/'paper/upstream_sources'/name
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=folder,text=True).strip()
    files={}
    for pattern in patterns:
        for path in folder.glob(pattern):
            if not path.is_file():continue
            h=hashlib.sha256()
            with path.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            files[path.relative_to(folder).as_posix()]=h.hexdigest()
    entry=dict(name=name,repository=url,paper_id=paper,commit=commit,local_path=folder.relative_to(ROOT).as_posix(),files=files,source_verified_at='2026-10-29',scope='Selected original entrypoints and native resources; algorithms not yet executed')
    lock=[item for item in lock if item['name']!=name]+[entry]
    print(json.dumps(dict(name=name,commit=commit,files=len(files))),flush=True)
lockpath.write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
