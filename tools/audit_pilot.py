"""Read-only reconciliation of available pilot outputs; never calls a provider."""
from pathlib import Path
from collections import Counter
import hashlib,json
from legalhub.benchmark import dataset
ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/'blocks/evaluator/artifacts/runs/20261004-vision-pilot'
MODELS=['sf_qwen38_thinking','sf_qwen3vl_instruct','sf_qwen3vl_thinking_native','kimi3_low','kimi26_nonthinking']

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    cohort=read(PILOT/'cohort.json');manifest,tasks=dataset()
    if cohort['dataset_sha256']!=manifest['dataset_sha256']:raise ValueError('Pilot dataset mismatch')
    ids=cohort['task_ids'];known={t['id'] for t in tasks}
    if len(ids)!=len(set(ids)) or not set(ids)<=known:raise ValueError('Invalid pilot IDs')
    outputs=[]
    for name in MODELS:
        folder=PILOT/name;spec=read(folder/'run.json')
        if spec['dataset_sha256']!=cohort['dataset_sha256'] or spec['task_ids']!=ids:raise ValueError('Different cohort: '+name)
        records={}
        for line in (folder/'predictions.jsonl').read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if row['id'] not in ids:raise ValueError('Unplanned prediction: '+name)
            records[row['id']]=row
        states=Counter(records.get(i,{'status':'missing'})['status'] for i in ids)
        metric=read(folder/'metrics.json')
        if sum(r['planned'] for r in metric)!=len(ids):raise ValueError('Wrong metrics denominator: '+name)
        if sum(r['ok'] for r in metric)!=states['ok']:raise ValueError('Metrics coverage mismatch: '+name)
        outputs.append({'configuration':name,'model':spec['model']['model_name'],'planned':len(ids),'states':dict(states),
                        'run':str((folder/'run.json').relative_to(ROOT)),
                        'predictions_sha256':hashlib.sha256((folder/'predictions.jsonl').read_bytes()).hexdigest()})
    result={'date':'2026-10-04','dataset_sha256':cohort['dataset_sha256'],'cohort_size':len(ids),'runs':outputs,
            'model_requests_by_this_audit':0,'conclusion':'Cohort and planned denominators consistent. Not a legal answer quality review or a full benchmark comparison.'}
    (ROOT/'reports/research/pilot_reconciliation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
