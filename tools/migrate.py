import os,shutil,json,hashlib,time,datetime,ast,tokenize,io,re,sys
from pathlib import Path
SOURCE=Path('D:/workspace');HUB=SOURCE/'screenshotLegalHub';PROJECTS=['ScreenshotLegalBench_v2','llm_evluator','Batch','labelU-Kit','silicon-pool','crawler-law','quiz-collector'];SKIP={'.git','node_modules','.venv','venv','__pycache__','.cache','.next','dist','build'}
manifest={'created_at':'2026-10-01','source_root':str(SOURCE),'destination_root':str(HUB),'projects':PROJECTS,'excluded_directories':sorted(SKIP),'files':[],'excluded':[],'path_changes':[],'errors':[]}
start=time.time()
for name in PROJECTS+['reports/ScreenshotLegalBench_v2']:
 src=SOURCE/name;dest=(HUB/'projects'/name) if name in PROJECTS else HUB/name
 print('COPY',name,flush=True)
 for base,dirs,files in os.walk(src):
  for d in list(dirs):
   if d in SKIP:
    dirs.remove(d);manifest['excluded'].append(str((Path(base)/d).relative_to(SOURCE)))
  for f in files:
   p=Path(base)/f
   if p.suffix.lower() in {'.pyc','.pyo'}:continue
   q=dest/p.relative_to(src);q.parent.mkdir(parents=True,exist_ok=True)
   if q.exists():raise RuntimeError('Destination already exists: '+str(q))
   before=p.stat();shutil.copy2(p,q)
   digest=hashlib.sha256()
   with q.open('rb') as stream:
    for chunk in iter(lambda:stream.read(4*1024*1024),b''):digest.update(chunk)
   after=p.stat()
   if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):manifest['errors'].append('Source changed during copy: '+str(p))
   manifest['files'].append({'source':p.relative_to(SOURCE).as_posix(),'destination':q.relative_to(HUB).as_posix(),'bytes':before.st_size,'source_mtime_ns':before.st_mtime_ns,'copied_sha256':digest.hexdigest()})
 print('COPIED',name,'files',len(manifest['files']),'elapsed',round(time.time()-start,1),flush=True)
(HUB/'migration_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(HUB/'hub_paths.py').write_text('''"""Resolve copied project paths relative to this hub."""\nfrom pathlib import Path\nHUB_ROOT = Path(__file__).resolve().parent\ndef project_path(project, relative=""):\n    return str(HUB_ROOT / "projects" / project / relative)\n''',encoding='utf-8')
# Path adaptation uses complete AST string literals, including adjacent strings.
import subprocess
subprocess.run([sys.executable, str(HUB / "tools" / "adapt_paths.py")], check=True)
print("COPY_AND_ADAPT_COMPLETE", len(manifest["files"]), flush=True)
