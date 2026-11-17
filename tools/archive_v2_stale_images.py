"""Archive orphaned images from early renders; never remove unarchived files."""
from pathlib import Path
from datetime import datetime,timezone
import sys,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,save,sha,processing_items
records=[]
for item in processing_items():
    d=OUT/'zh'/item['id']
    if read(d/'status.json')['phase']!='rendered':continue
    shots=d/'screenshots';assert shots.resolve().is_relative_to(OUT.resolve())
    current={i['path'] for i in read(d/'render.json')['images']}
    for old in shots.glob('*.png'):
        if old.relative_to(d).as_posix() in current:continue
        assert old.resolve().parent==shots.resolve()
        archive=d/'render.versions'/('orphaned_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
        archive.mkdir(parents=True,exist_ok=False);target=archive/old.name
        shutil.copyfile(old,target);assert sha(old.read_bytes())==sha(target.read_bytes())
        records.append({'case_id':item['id'],'previous_path':old.relative_to(d).as_posix(),
            'archive':target.relative_to(d).as_posix(),'sha256':sha(target.read_bytes())})
        old.unlink()
log=OUT/'stale_image_archive.json'
previous=read(log) if log.exists() else {}
history=previous.get('archive_history',previous.get('archived_this_run',[]))
save(log,{'archived_this_run':records,'archive_history':history+records,'destructive_without_archive':False})
print({'orphaned_images_archived':len(records)})
