import json,sys
from pathlib import Path
root=Path.cwd();sys.path[:0]=[str(root/'product_v1/backend/src'),str(root)]
from paper.author_reproductions import run_per_paper_validation as base
from screenshotlegal.research.store import Store
conf=base.base.ReadOnlyConfiguration(root/'product_v1/data');owner=conf.get('model_configs',base.base.MODEL_ID)['owner_id'];s=Store(base.OUT/'.runtime')
rows=[]
for a in s.list('benchmark.attempt',owner):
    if a['status']!='completed' or a.get('response',{}).get('demo') or a.get('pipeline_id'):continue
    r=s.get('benchmark.run',a['run_id'],owner);t=next(t for t in r['tasks'] if t['task_id']==a['task_id'])
    rows.append(dict(attempt=a['id'],run=r['id'],track=r['track'],task_id=t['task_id'],family=t['task_family'],input_keys=list(t['input']),answer_kind=t.get('answer_kind'),run_keys=list(r),asset=t['asset']['sha256']))
print(json.dumps(rows,ensure_ascii=False));s.close()
