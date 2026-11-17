import pytest
from screenshotlegal.research.history import history
from screenshotlegal.research.contracts import EvaluationCreate,now
from test_research_products import lab,release,drain
from test_accounts_ingestion import accounts

async def test_history_unifies_trials_formal_runs_and_capability_without_rewriting(lab):
    _,published=await release(lab)
    run=lab.evaluation.create_run('alice',EvaluationCreate(name='Formal fixture',release_id=published['id'],model_ids=['demo'],idempotency_key='history'))
    await drain(lab)
    with lab.store.tx() as db:
        lab.store.put('research.flow',dict(id='trial',name='Real trial fixture',status='awaiting_human_review',created_at=now(),summary=dict(qa_requests=2,qa_success=1,requests_unknown=1,qa_by_mode={'text':1,'multi_image':1})),'alice',db)
        lab.store.put('research.flow',dict(id='software',name='Software only',status='completed',created_at=now(),summary=dict(flow_type='software_verification',qa_requests=99)),'alice',db)
        for id,owner,scope,flow,success in [('grouped','alice','development_qa','trial',True),('capability','alice','capability','trial',False),('orphan','alice','development_qa','no-flow',False),('private','bob','development_qa','trial',True)]:
            lab.store.put('evaluation.probe',dict(id=id,scope=scope,flow_id=flow,created_at=now(),success=success,mode='text',model_snapshot={'name':'Mock','encrypted_api_key':'SECRET'},response={'raw':'PRIVATE RESPONSE'},error={'unknown':not success}),'alice' if owner=='alice' else 'bob',db)
        before={t:[tuple(x) for x in db.execute('SELECT * FROM '+t)] for t in ['records','jobs','idempotency','audit_events']}
    result=history(lab.store,'alice')
    assert result['summary']==dict(formal_runs=1,trial_flows=1,recorded_probes=3,counts=dict(formal=1,trial=2,capability=1))
    assert len(result['items'])==4 and {r['id'] for r in result['items']}=={run['id'],'trial','capability','orphan'}
    assert 'SECRET' not in str(result) and 'PRIVATE RESPONSE' not in str(result)
    flow=next(r for r in result['items'] if r['id']=='trial')
    assert flow['scoring']=='unscored' and flow['returned']==1 and flow['unknown']==1
    assert next(r for r in result['items'] if r['id']=='capability')['status']=='unknown'
    assert len(history(lab.store,'alice','trial')['items'])==2
    assert history(lab.store,'alice','formal')['items'][0]['id']==run['id']
    first=history(lab.store,'alice',limit=2);second=history(lab.store,'alice',offset=first['next_offset'],limit=2)
    assert not {r['id'] for r in first['items']} & {r['id'] for r in second['items']}
    assert {r['id'] for r in history(lab.store,'bob')['items']}=={'private'}
    assert history(lab.store,'nobody')['total']==0
    for args in [dict(category='bad'),dict(offset=-1),dict(limit=0),dict(limit=101)]:
        with pytest.raises(ValueError):history(lab.store,'alice',**args)
    with lab.store.read() as db:
        assert before=={t:[tuple(x) for x in db.execute('SELECT * FROM '+t)] for t in before}

def test_history_http_requires_owner_and_does_not_create_formal_runs(accounts):
    _,admin,alice,bob=accounts
    probe=alice.post('/v1/evaluation/models/demo/test',json={'mode':'text'}).json()
    result=alice.get('/v1/evaluation/history').json()
    assert result['summary']['formal_runs']==0 and result['summary']['recorded_probes']==1
    assert result['items'][0]['id']==probe['id'] and result['items'][0]['category']=='capability'
    assert bob.get('/v1/evaluation/history').json()['items']==[]
    assert alice.get('/v1/evaluation/runs').json()==[]
    assert alice.get('/v1/evaluation/history?category=bad').status_code==422
    alice.post('/v1/auth/logout')
    assert alice.get('/v1/evaluation/history').status_code==401
