import asyncio
import json
import time
import pytest
from test_accounts_ingestion import accounts,model
from screenshotlegal.experiments.registry import CandidateRegistry
from screenshotlegal.experiments.budget import BudgetTracker,BudgetExceeded
from screenshotlegal.experiments.inputs import SourceReader
from screenshotlegal.experiments.engine import validate_output

def create_case(client,text='公开原文 金额 520 元。',title='实验案件'):
    cid=client.post('/v1/cases',json=dict(title=title,description='GOLD_HIDDEN_NOT_INPUT')).json()['id']
    doc=client.post('/v1/cases/'+cid+'/documents',files={'file':('notes.txt',text.encode(),'text/plain')}).json()
    assert client.post('/v1/cases/'+cid+'/documents/'+doc['id']+'/parse-next',json=dict(pages=3)).status_code==200
    return cid,doc
def payload(cid,doc,**changes):
    value=dict(case_id=cid,name='对照试验',goal='核对公开材料',method_ids=['E00'],document_ids=[doc['id']],model_id='demo',
               case_group_id='group-'+cid,split='development',law_effective_date='2024-01-01',idempotency_key='test-'+cid)
    value.update(changes);return value
def wait_run(client,id):
    for _ in range(100):
        result=client.get('/v1/evaluation/agent-runs/'+id)
        assert result.status_code==200,result.text
        value=result.json()
        if value['run']['status'] not in ['queued','running']:return value
        time.sleep(.03)
    raise AssertionError('experiment did not finish')

def test_catalog_validates_all_references_and_rejects_unimplemented_method():
    registry=CandidateRegistry()
    assert len(registry.methods)==24 and len(registry.papers)==51
    assert registry.method('E06')['steps']==['identify','map_evidence','synthesize','verify','revise']
    with pytest.raises(ValueError,match='尚未实现'):registry.method('E04')
    assert all(p['runtime_verification']=='not_reproduced' for p in registry.public()['papers'])

def test_six_methods_run_on_same_document_only_input_without_gold_or_quality_scores(accounts):
    _,_,alice,_=accounts
    cid,doc=create_case(alice)
    assert alice.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending')).status_code==200
    p=payload(cid,doc,allow_draft_matter=True,method_ids=['E00','E01','E02','E03','E05','E06'])
    preview=alice.post('/v1/evaluation/agent-preview',json=p)
    assert preview.status_code==200,preview.text
    assert preview.json()['sources']>0
    cohort=alice.post('/v1/evaluation/agent-runs',json=p)
    assert cohort.status_code==201,cohort.text
    ids=cohort.json()['run_ids'];assert len(ids)==6
    results=[wait_run(alice,id) for id in ids]
    assert all(r['run']['status']=='completed' for r in results),[(r['run']['method']['id'],r['run'].get('error')) for r in results]
    assert len({r['run']['input_digest'] for r in results})==1
    assert all(r['run']['scoring_status']=='unscored_demo' for r in results)
    assert all(r['run']['engineering_metrics']['citation_support_accuracy'] is None for r in results)
    assert {r['run']['method']['id']:r['run']['usage']['model_calls'] for r in results}==dict(E00=1,E01=2,E02=3,E03=3,E05=4,E06=5)
    assert results[1]['tools'][0]['tool']=='source_read'
    assert results[0]['graph']['entities'][0]['kind']=='fact'
    assert 'GOLD_HIDDEN_NOT_INPUT' not in json.dumps(results)
    assert all('credential_ref' not in r['run']['model'] for r in results)
    assert alice.post('/v1/evaluation/agent-runs',json=p).json()['run_ids']==ids
    comparison=alice.get('/v1/evaluation/agent-comparison',params={'ids':','.join(ids)}).json()
    assert comparison['fixed_factors_match'] and not comparison['legal_quality_comparable']
    assert not comparison['measured_usage_comparable']

def test_snapshots_are_immutable_and_char_reader_preserves_exact_unicode_range(accounts):
    _,_,alice,bob=accounts
    cid,doc=create_case(alice,'甲😀乙'+'很长原文'*1000)
    snap=alice.app.state.documents.store.freeze(cid,doc['id'])
    assert snap==alice.app.state.documents.store.freeze(cid,doc['id'])
    assert alice.get('/v1/cases/'+cid+'/document-snapshots/'+snap['id']).status_code==200
    assert bob.get('/v1/cases/'+cid+'/document-snapshots/'+snap['id']).status_code==404
    p=payload(cid,doc)
    runid=alice.post('/v1/evaluation/agent-runs',json=p).json()['run_ids'][0]
    run=wait_run(alice,runid);reader=SourceReader(dict(sources=run['sources'],legal_corpus=[]))
    ref=run['sources'][0];parts=[];args=dict(source_ref_id=ref['id'],start=0,max_chars=7)
    while True:
        chunk=reader.execute('source_read',args);parts.append(chunk['text'])
        if not chunk['next_request']:break
        args=chunk['next_request']['args']
    assert ''.join(parts)==ref['text']
    with pytest.raises(ValueError):reader.execute('source_read',dict(source_ref_id='other'))
    with pytest.raises(ValueError):reader.execute('shell',dict(command='arbitrary'))
    with alice.app.state.documents.store.tx() as db:
        row=alice.app.state.documents.store.get(cid,doc['id'],db);row['version']+=1;alice.app.state.documents.store.put(row,db)
    stale=alice.get('/v1/evaluation/agent-runs/'+runid).json()
    assert stale['staleness']['stale']
    assert stale['run']['output_digest']==run['run']['output_digest']

def test_permissions_catalog_and_case_group_split_guard(accounts):
    _,admin,alice,bob=accounts
    cid,doc=create_case(alice)
    p=payload(cid,doc)
    assert bob.post('/v1/evaluation/agent-runs',json=p).status_code==404
    first=alice.post('/v1/evaluation/agent-runs',json=p).json()
    assert bob.get('/v1/evaluation/agent-runs/'+first['run_ids'][0]).status_code==404
    assert admin.get('/v1/evaluation/agent-runs/'+first['run_ids'][0]).status_code==404
    assert alice.post('/v1/evaluation/agent-runs',json=dict(p,method_ids=['E04'],idempotency_key='planned')).status_code==409
    assert alice.post('/v1/evaluation/agent-runs',json=dict(p,split='holdout',idempotency_key='bad-split')).status_code==409
    cid2,doc2=create_case(alice)
    assert alice.post('/v1/evaluation/agent-runs',json=payload(cid2,doc2,split='holdout')).status_code==409
    alice.put('/v1/cases/'+cid+'/members',json=dict(username='bob',role='viewer'))
    assert bob.post('/v1/evaluation/agent-runs',json=p).status_code==403

def test_budget_rejects_before_external_calls_and_counts_actual_usage():
    budget=dict(max_input_tokens=100,max_output_tokens=100,max_model_calls=1,max_tool_calls=0,max_wall_time_s=5,max_output_per_call=100)
    tracker=BudgetTracker(budget)
    with pytest.raises(BudgetExceeded):tracker.reserve([dict(role='user',content='input')])
    assert tracker.usage['model_calls']==0
    budget['max_input_tokens']=10000
    tracker=BudgetTracker(budget);assert tracker.reserve([])==100
    assert tracker.charge(dict(usage=dict(prompt_tokens=12,completion_tokens=7)))
    assert tracker.usage['input_tokens']==12
    with pytest.raises(BudgetExceeded):tracker.reserve([])
    with pytest.raises(BudgetExceeded):tracker.tool()
    assert not tracker.charge(dict(usage=dict(prompt_tokens=True,completion_tokens=2)))
    assert tracker.usage['missing_usage_calls']==1

def test_grounding_checks_spans_foreign_refs_and_links():
    sources=[dict(id='r1',text='甲😀乙')]
    good=dict(summary='摘要',facts=[dict(id='f',statement='事实',citations=[dict(source_ref_id='r1',quote='😀',start=1,end=2)])],
              evidence_links=[dict(fact_id='f',source_ref_id='r1',relation='context',quote='😀')])
    assert validate_output(good,dict(sources=sources))['facts']
    for quote,start,end in [('甲',1,2),('😀',2,3),('甲😀乙',0,99)]:
        bad=json.loads(json.dumps(good));bad['facts'][0]['citations'][0].update(quote=quote,start=start,end=end)
        with pytest.raises(ValueError):validate_output(bad,dict(sources=sources))
    bad=json.loads(json.dumps(good));bad['facts'][0]['citations'][0]['source_ref_id']='foreign'
    with pytest.raises(ValueError):validate_output(bad,dict(sources=sources))

def test_budget_and_missing_usage_stop_runs_without_automatic_retry(accounts,monkeypatch):
    _,_,alice,_=accounts;cid,doc=create_case(alice)
    tiny=payload(cid,doc,budget=dict(max_input_tokens=100))
    rid=alice.post('/v1/evaluation/agent-runs',json=tiny).json()['run_ids'][0]
    result=wait_run(alice,rid)
    assert result['run']['status']=='failed' and result['run']['error']['category']=='budget_exhausted'
    assert result['run']['usage']['model_calls']==0
    m=model(alice)
    calls=[]
    async def missing(*args):
        calls.append(args);return dict(raw='{}',usage=None,latency_ms=1,demo=False)
    service=alice.app.state.research['agent_experiments']
    monkeypatch.setattr(service.gateway,'call',missing)
    p=payload(cid,doc,model_id=m['id'],method_ids=['E02'],idempotency_key='missing-usage')
    rid=alice.post('/v1/evaluation/agent-runs',json=p).json()['run_ids'][0]
    result=wait_run(alice,rid)
    assert result['run']['status']=='failed' and result['run']['error']['category']=='usage_missing'
    assert len(calls)==1 and len(result['steps'])==1
    assert result['run']['usage']['missing_usage_calls']==1
