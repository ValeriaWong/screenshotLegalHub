from uuid import uuid4
from screenshotlegal.domain.common.models import now

def emit(repo, run_id, event, payload=None):
    existing=repo.list('run_events',run_id=run_id)
    item=dict(id=str(uuid4()),sequence=len(existing)+1,event=event,data=payload or {},created_at=now())
    repo.put('run_events',item['id'],item,run_id=run_id,immutable=True)
    return item

def snapshot(repo,run_id):
    run=repo.get('analysis_runs',run_id)
    audits=repo.list('skill_runs',run_id=run_id)
    nodes={n['node_id']:'PENDING' for n in run['plan']['nodes']}
    mapping={'node-started':'RUNNING','node-completed':'COMPLETED','node-failed':'FAILED'}
    for e in sorted(repo.list('run_events',run_id=run_id),key=lambda e:e['sequence']):
        if e['event'] in mapping:
            nodes[e['data']['node_id']]=mapping[e['event']]
    for id,status in list(nodes.items()):
        if run['status']=='INTERRUPTED' and status=='RUNNING':nodes[id]='INTERRUPTED'
        if run['status']=='FAILED' and status=='PENDING':nodes[id]='SKIPPED'
        if run['status']=='WAITING_REVIEW' and status=='PENDING':nodes[id]='WAITING_REVIEW'
    return dict(run=run,skill_runs=audits,gates=repo.list('review_gates',run_id=run_id),node_states=nodes)
