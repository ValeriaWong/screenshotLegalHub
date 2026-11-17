"""Author cores in the case product route; deterministic transport, zero supplier calls."""
import json,time
import pytest
from test_accounts_ingestion import accounts
from test_agent_experiments import create_case,payload

@pytest.mark.parametrize('method',['E15','E16','E21'])
def test_author_case_exports_original_structure_and_grounded_output(accounts,method):
    _,_,alice,bob=accounts
    cid,doc=create_case(alice,'甲说：已付款520元。乙说：尚未核对到账。')
    p=payload(cid,doc,method_ids=[method],budget=dict(max_model_calls=20,max_wall_time_s=120),idempotency_key='author-case-'+method)
    response=alice.post('/v1/evaluation/agent-runs',json=p)
    assert response.status_code==201,response.text
    rid=response.json()['run_ids'][0]
    deadline=time.monotonic()+75
    while time.monotonic()<deadline:
        result=alice.get('/v1/evaluation/agent-runs/'+rid).json()
        if result['run']['status'] not in ['queued','running']:break
        time.sleep(.1)
    assert result['run']['status']=='completed',result['run'].get('error')
    assert result['run']['scoring_status']=='unscored_demo'
    assert result['run']['engineering_metrics']['citation_support_accuracy'] is None
    assert len(result['author_artifacts'])==1
    artifact=result['author_artifacts'][0]
    assert artifact['sha256'] and artifact['reproduction_name']==result['reproduction_name']
    assert artifact['execution']['original_complete_benchmark'] is False
    if method=='E15':assert artifact['execution']['tree']['nodes']
    elif method=='E16':assert artifact['execution']['graph']['nodes'] and artifact['execution']['graph']['edges']
    else:assert artifact['execution']['trials']
    assert 'GOLD_HIDDEN_NOT_INPUT' not in json.dumps(result,ensure_ascii=False)
    assert result['run']['output']['facts'][0]['citations']
    assert bob.get('/v1/evaluation/agent-runs/'+rid).status_code==404
    assert all(s['reproduction_name']==result['reproduction_name'] for s in result['steps'])
