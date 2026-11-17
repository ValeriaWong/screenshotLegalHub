"""Regressions observed in recorded real model responses, using zero new API calls."""
import json
from test_author_benchmark_adapter import setup
from test_research_products import lab,drain
from test_accounts_ingestion import accounts

async def test_react_chat_action_prefix_is_mapped_without_fake_tool_observation(lab):
    b,p,calls=setup(lab,'vqa',max_calls=14,raw=lambda n:'Action 1: Finish[{"answer":"non_legal_dialog","evidence":[]}]')
    p['method_id']='E01';run=b.create_run('alice',p);await drain(lab)
    result=b.results('alice',run['id'])
    assert result['run']['status']=='completed' and len(calls)==1
    step=result['method_steps'][0]
    assert step['response']['raw'].startswith('Action 1: Finish[')
    assert '\nObservation' in step['effective_parameters']['stop']
    artifact=result['attempts'][0]['response']['author_execution']
    assert len(artifact['transport_normalizations'])==1
    assert not result['method_tools']

async def test_self_refine_observed_completion_suffix_keeps_json_values(lab):
    def raw(n):
        if n%2==0:return 'Scores:\nIssues: 保留未知\nTotal score: 24/25'
        return ('carefully.Response: ' if n==3 else 'Response: ')+json.dumps(dict(answer='non_legal_dialog',evidence=['#Response:原文']),ensure_ascii=False)
    b,p,calls=setup(lab,'vqa',raw=raw);run=b.create_run('alice',p);await drain(lab)
    result=b.results('alice',run['id'])
    assert result['run']['status']=='completed' and len(calls)==4
    assert result['attempts'][0]['parsed']['evidence']==['#Response:原文']
    assert next(s for s in result['method_steps'] if s['stage']=='revise.1')['response']['raw'].startswith('carefully.Response:')
