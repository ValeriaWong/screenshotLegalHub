"""Pinned SCALE components with deterministic transport; no model weights or supplier calls."""
import json
import pytest
from test_accounts_ingestion import accounts
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.experiments.engine import SYSTEM_POLICY, demo_analysis, validate_output
from screenshotlegal.experiments.inputs import citation_units
from screenshotlegal.research.contracts import digest


@pytest.mark.parametrize('provided',[False,True])
async def test_scale_original_components_product_source_only_hierarchy(provided):
    source=dict(id='case-source',text='CASE_ONLY_9841：甲说已转账，乙说未核实。',text_digest=digest('CASE_ONLY_9841：甲说已转账，乙说未核实。'))
    source['citation_units']=citation_units(source['text'])
    law=dict(id='law:1',text='INDEPENDENT_LAW_ONLY：主张者应当提交支持其主张的证据。',verification_status='draft')
    hierarchy=[dict(id='issue:1',label='请求证据是否充分',factors=[dict(id='factor:1',label='存在支持证据',guide_source_ids=['law:1'])])]
    visible=dict(goal='QUESTION_ONLY_5732 核对主张',sources=[source],legal_corpus=[law],matterpack=dict(factor_hierarchy=hierarchy) if provided else {})
    requests=[];artifacts=[]
    async def raw(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages))
        if stage.startswith('guide_'):answer='Issue 1: 请求证据是否充分 (¶1)\n  Factor A: 存在支持证据 (¶1)'
        elif stage.startswith('issues.'):answer='Issue 1: 请求证据是否充分'+('' if provided else ' (¶1)')
        elif stage.startswith('factors.'):answer='Factor A: 存在支持证据 (¶1)'
        elif stage.startswith('reasoning.'):answer='待核实转账陈述，适用独立法源¶1；缺少银行到账核验。'
        else:answer=json.dumps(demo_analysis(dict(sources=[source])),ensure_ascii=False)
        return dict(raw=answer)
    async def artifact(name,result):artifacts.append(result)
    async def generic(*args):raise AssertionError('SCALE must execute author stages, not generic staged baseline')
    result=await run_method('E19',visible,[source],generic,generic,SYSTEM_POLICY,lambda:{},{},raw_call=raw,author_record=artifact)
    validate_output(result,dict(sources=[source]))
    assert len(artifacts)==1
    actual=artifacts[0]
    assert actual['paths']['guide_paragraph_ids']==[1]
    assert actual['paths']['updates'] and actual['source_commit']=='1700924ca8c448af56c854e5e4c9ae693e86beb3'
    assert actual['paragraphs']['1']['source_id']=='law:1'
    assert actual['original_complete_benchmark'] is False and actual['local_model_inference'] is False
    assert actual['hierarchy_review_status']=='not_expert_reviewed'
    guides=[r for r in requests if r['stage'].startswith('guide_')]
    assert len(guides)==(0 if provided else 2)
    for r in guides:
        text=json.dumps(r['messages'],ensure_ascii=False)
        assert 'CASE_ONLY_9841' not in text and 'QUESTION_ONLY_5732' not in text
    assert 'CASE_ONLY_9841' in json.dumps(requests[-1]['messages'],ensure_ascii=False)
    assert len(requests)==(4 if provided else 6)


async def test_scale_rejects_guide_reference_not_in_frozen_law():
    from screenshotlegal.method_reproductions.scale_bridge import scale_case
    from screenshotlegal.method_reproductions.context import MethodContext
    async def raw(stage,messages,parameters):return dict(raw='Issue 1: fabricated (¶999)\n  Factor A: fabricated (¶999)')
    context=MethodContext(dict(goal='q',sources=[],matterpack={},legal_corpus=[dict(id='law',text='independent source')]),[],None,None,'policy',lambda:{},{},raw_call=raw)
    with pytest.raises(ValueError,match='有效¶引用'):await scale_case(context)


def test_scale_case_http_dispatch_and_artifact_export(accounts):
    import time
    from test_agent_experiments import create_case,payload
    _,_,client,_=accounts
    cid,doc=create_case(client,'甲说：已付款520元。乙说：未核实到账。')
    client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending'))
    response=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,method_ids=['E19'],allow_draft_matter=True,budget=dict(max_model_calls=20,max_wall_time_s=120)))
    assert response.status_code==201,response.text
    rid=response.json()['run_ids'][0]
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        result=client.get('/v1/evaluation/agent-runs/'+rid).json()
        if result['run']['status'] not in ['queued','running']:break
        time.sleep(.1)
    assert result['run']['status']=='completed',result['run'].get('error')
    assert result['run']['scoring_status']=='unscored_demo'
    assert result['reproduction_name']=='e19_scale'
    assert result['author_artifacts'][0]['execution']['paths']['guide_paragraph_ids']==[1]
    assert result['author_artifacts'][0]['execution']['local_model_inference'] is False
    assert 'GOLD_HIDDEN_NOT_INPUT' not in json.dumps(result,ensure_ascii=False)
    exported=client.get('/v1/evaluation/agent-runs/'+rid+'/export')
    assert exported.status_code==200 and 'e19_scale.' in exported.headers['content-disposition']
