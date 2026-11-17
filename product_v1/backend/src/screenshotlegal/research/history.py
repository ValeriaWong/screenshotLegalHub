"""Read-only evaluation history over existing owner-scoped records; never promote probes."""
from .operations import operation_url

def history(store, owner, category='all', offset=0, limit=20):
    if category not in ['all','formal','trial','capability','benchmark']:
        raise ValueError('不支持的运行记录类型')
    if offset<0 or not 1<=limit<=100:
        raise ValueError('无效分页')
    with store.read() as db:
        runs=store.list('evaluation.run',owner,db)
        probes=store.list('evaluation.probe',owner,db)
        flows=[f for f in store.list('research.flow',owner,db)
               if f.get('summary',{}).get('flow_type')!='software_verification'
               and isinstance(f.get('summary',{}).get('qa_requests'),int)]
    items=[]
    covered={f['id'] for f in flows}
    for r in runs:
        items.append(dict(id=r['id'],kind='evaluation.run',category='formal',name=r['name'],
                          status=r['status'],created_at=r['created_at'],modes=[r['mode']],
                          total=len(r['tasks']),returned=None,scoring='per_question',
                          href='/evaluation.html?run='+r['id'],unknown=None))
    for f in flows:
        s=f['summary']
        items.append(dict(id=f['id'],kind='research.flow',category='trial',name=f['name'],
                          status=f['status'],created_at=f['created_at'],
                          modes=list(s.get('qa_by_mode',{})),total=s['qa_requests'],
                          returned=s.get('qa_success'),scoring='unscored',
                          unknown=s.get('requests_unknown'),href=operation_url('research.flow',f['id'])))
    for p in probes:
        capability=p.get('scope')=='capability'
        if not capability and p.get('flow_id') in covered:
            continue
        model=p.get('model_snapshot',{})
        status='completed' if p.get('success') else 'unknown' if (p.get('error') or {}).get('unknown') else 'failed'
        items.append(dict(id=p['id'],kind='evaluation.probe',category='capability' if capability else 'trial',
                          name=(model.get('name') or model.get('model') or '模型')+(' · 连通性测试' if capability else ' · 样本问答试跑'),
                          status=status,created_at=p['created_at'],modes=[p['mode']],total=1,
                          returned=1 if p.get('success') else 0,scoring='unscored',
                          unknown=1 if status=='unknown' else 0,href=operation_url('evaluation.probe',p['id'])))
    for r in store.list('benchmark.history',owner):
        items.append(dict(id=r['id'],kind='benchmark.history',category='benchmark',name='历史导入 · '+r['name'],status=r['status'],created_at=r['created_at'],modes=[r['role']],total=r['summary']['rows'],returned=None,scoring='historical_unverified',unknown=None,href=operation_url('benchmark.history',r['id'])))
    for r in store.list('benchmark.pipeline',owner):
        items.append(dict(id=r['id'],kind='benchmark.pipeline',category='benchmark',name='按图流程 · '+r['name'],status=r['status'],created_at=r['created_at'],modes=list(r['variants']),total=r['planned_units'],returned=(r.get('execution_counts') or {}).get('response_received',0),scoring=r['mode'],unknown=(r.get('execution_counts') or {}).get('unknown',0),href='/evaluation.html?benchmark=1&pipeline='+r['id']))
    for r in store.list('benchmark.run',owner):
        items.append(dict(id=r['id'],kind='benchmark.run',category='benchmark',name=r['name'],status=r['status'],created_at=r['created_at'],modes=[r['track']],total=r.get('counts',{}).get('planned',len(r.get('task_ids',[]))),returned=None,scoring=r['mode'],unknown=None,href='/evaluation.html?benchmark=1&benchmark_run='+r['id']))
    counts={c:sum(r['category']==c for r in items) for c in ['formal','trial','capability']}
    if any(r['category']=='benchmark' for r in items): counts['benchmark']=sum(r['category']=='benchmark' for r in items)
    rows=sorted([r for r in items if category=='all' or r['category']==category],
                key=lambda r:(r['created_at'],r['kind'],r['id']),reverse=True)
    return dict(items=rows[offset:offset+limit],total=len(rows),
                next_offset=offset+limit if offset+limit<len(rows) else None,
                summary=dict(formal_runs=len(runs),trial_flows=len(flows),recorded_probes=len(probes),counts=counts))
