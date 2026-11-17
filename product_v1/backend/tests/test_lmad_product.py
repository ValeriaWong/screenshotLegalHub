"""L-MAD case/binary-VQA adapters, budgets and original-component dispatch; no paid calls."""
import json
import pytest
from screenshotlegal.method_reproductions.e09_l_mad import run_task
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.experiments.engine import demo_analysis,SYSTEM_POLICY,validate_output
from screenshotlegal.experiments.inputs import citation_units
from test_accounts_ingestion import accounts
from test_research_products import lab

async def test_non_entailment_is_not_mapped_to_the_opposite_label():
    async def raw(stage,messages,parameters):return dict(raw='[AGREE]\nAnswer:N')
    task=dict(track='vqa_predicted_text',task_type='vqa.categorical',question='群聊或私聊？',allowed_values=['group_chat','private_chat'],upstream_prediction={'conversation':[{'content':'hello'}]})
    result=await run_task([dict(role='system',content='JSON answer/evidence'),dict(role='user',content=json.dumps(task))],raw)
    assert result['output']['answer'] is None
    assert [r['result']['output']['answer'] for r in result['binary_checks']]==['N','N']
    assert result['mapping'].startswith('both labels independently tested')

async def test_four_way_task_is_rejected_before_any_model_request():
    calls=[]
    async def raw(*args):calls.append(args);return dict(raw='Answer:Y')
    task=dict(track='vqa_predicted_text',task_type='vqa.categorical',question='分类',allowed_values=['a','b','c','d'],upstream_prediction={'conversation':[{'content':'hello'}]})
    with pytest.raises(ValueError,match='exactly two'):
        await run_task([dict(role='system',content='JSON'),dict(role='user',content=json.dumps(task))],raw)
    assert calls==[]

async def test_case_revision_only_retains_protocol_supported_facts():
    source=dict(id='s1',text='甲称已付款，乙称待核对。',citation_units=citation_units('甲称已付款，乙称待核对。'))
    original=dict(elements=[],**demo_analysis({'sources':[source]}));calls=[];artifacts=[]
    async def raw(stage,messages,parameters):
        calls.append(stage)
        if stage=='case.propose':return dict(raw=json.dumps(original,ensure_ascii=False))
        if stage=='case.revise':return dict(raw=json.dumps({k:v for k,v in json.loads(messages[-1]['content'])['candidate'].items() if k!='facts'},ensure_ascii=False))
        return dict(raw='[AGREE]\nAnswer:N')
    async def generic(*args):raise AssertionError('Old E09 staged baseline must not execute')
    async def artifact(name,result):artifacts.append(result)
    output=await run_method('E09',dict(goal='核对陈述',sources=[source]),[source],generic,generic,SYSTEM_POLICY,lambda:original,
        dict(max_model_calls=20,lmad_protocol='hybrid',lmad_rounds=3),raw_call=raw,author_record=artifact)
    validate_output(output,dict(sources=[source]))
    assert output['facts']==[] and output['evidence_links']==[]
    assert any('非证伪' in x for x in output['uncertainties'])
    assert len(calls)==7 and artifacts[0]['verified_facts']==[]


def test_lmad_http_case_executes_paper_protocol_not_old_generic_debate(accounts):
    import time
    from test_agent_experiments import create_case,payload
    _,_,client,_=accounts
    cid,doc=create_case(client,'甲称已经付款，乙称尚待核对。')
    client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending'))
    result=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,method_ids=['E09'],allow_draft_matter=True))
    assert result.status_code==201,result.text
    rid=result.json()['run_ids'][0];deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        data=client.get('/v1/evaluation/agent-runs/'+rid).json()
        if data['run']['status'] not in ['queued','running']:break
        time.sleep(.1)
    assert data['run']['status']=='completed',data['run'].get('error')
    assert data['run']['scoring_status']=='unscored_demo'
    execution=data['author_artifacts'][0]['execution']
    assert execution['upstream_component_code_executed'] is True and execution['LMAD_author_code_executed'] is False
    assert execution['binary_checks'] and execution['verification_scope'].startswith('source-statement support')
    assert client.get('/v1/evaluation/agent-runs/'+rid+'/export').status_code==200


async def test_benchmark_protocol_and_real_generation_parameters_are_frozen(lab):
    from test_benchmark_pipeline import setup
    from test_benchmark_migration import prompt
    from test_research_products import drain
    pipeline,p,_,benchmark=setup(lab);row=pipeline.create('alice',p);await drain(lab)
    upstream=next(a for a in lab.store.list('benchmark.attempt','alice') if a.get('pipeline_id')==row['id'] and a['task_family']=='kie.extract')
    vp=prompt(benchmark,'vqa');observed=[]
    async def transport(owner,model,messages,purpose,request_id):
        observed.append(dict(model=model,messages=messages))
        if ':candidate.0.' in request_id:raw='[AGREE]\nAnswer:Y'
        else:raw='[AGREE]\nAnswer:N'
        return dict(raw=raw,usage=dict(prompt_tokens=20,completion_tokens=10,total_tokens=30),latency_ms=1,cost_estimate=0,cost_currency='CNY',demo=False)
    lab.gateway._call=transport
    payload=dict(dataset_id=p['dataset_id'],name='L-MAD binary VQA',task_ids=['global'],track='vqa_predicted_text',mode='development_reference',release_id=None,
        model_id='local-fixture',prompt_id=vp['id'],method_id='E09',method_protocol='hybrid',method_attempts=2,method_max_output_tokens=6144,max_calls=18,
        iou_threshold=.6,upstream_attempt_id=upstream['id'],idempotency_key='lmad-binary')
    run=benchmark.create_run('alice',payload);await drain(lab);result=benchmark.results('alice',run['id'])
    assert result['run']['status']=='completed',result['attempts']
    assert result['run']['method']['protocol']=='hybrid'
    assert result['attempts'][0]['parsed']['answer']=='is_evidence'
    assert len(observed)==10 and all(r['model']['parameters']['temperature']==.1 and r['model']['parameters']['max_tokens']==1024 for r in observed)
    assert 'LEGACY_PRIVATE_ANSWER' not in json.dumps(observed)

async def test_dangling_proposal_reference_is_rejected_before_any_debate_call():
    source=dict(id='s1',text='甲称已付款。',citation_units=citation_units('甲称已付款。'))
    candidate=dict(elements=[],**demo_analysis({'sources':[source]}))
    candidate['claims']=[dict(id='c1',label='候选请求',applicability='uncertain',fact_ids=['not-generated'])]
    calls=[]
    async def raw(stage,messages,parameters):
        calls.append(stage)
        assert '只能引用本次facts数组里实际存在的id' in messages[0]['content']
        return dict(raw=json.dumps(candidate,ensure_ascii=False))
    async def generic(*args):raise AssertionError('No generic path')
    with pytest.raises(ValueError,match='请求引用未知事实'):
        await run_method('E09',dict(goal='核对',sources=[source]),[source],generic,generic,SYSTEM_POLICY,lambda:candidate,dict(max_model_calls=20),raw_call=raw)
    assert calls==['case.propose']


async def test_revision_cannot_reintroduce_rejected_facts():
    source=dict(id='s1',text='甲称已付款。',citation_units=citation_units('甲称已付款。'))
    candidate=dict(elements=[],**demo_analysis({'sources':[source]}));calls=[]
    async def raw(stage,messages,parameters):
        calls.append(stage)
        if stage in {'case.propose','case.revise'}:return dict(raw=json.dumps(candidate,ensure_ascii=False))
        return dict(raw='[AGREE]\nAnswer:N')
    async def generic(*args):raise AssertionError('No generic path')
    with pytest.raises(ValueError,match='five mutable fields'):
        await run_method('E09',dict(goal='核对',sources=[source]),[source],generic,generic,SYSTEM_POLICY,lambda:candidate,dict(max_model_calls=20),raw_call=raw)
    assert calls[-1]=='case.revise'
