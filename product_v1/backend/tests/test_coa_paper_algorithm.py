"""CoA Algorithm 1 contract checks with scripted API transport; no local neural model."""
import json
import pytest
from screenshotlegal.method_reproductions.paper_bridge import execute
from screenshotlegal.method_reproductions import run_method
from screenshotlegal.experiments.engine import demo_analysis,SYSTEM_POLICY,validate_output
from screenshotlegal.experiments.inputs import citation_units
from test_accounts_ingestion import accounts
from test_research_products import lab


def request(**changes):
    return dict(text='UNIQUE_ALPHA_SOURCE '+('alpha beta gamma '*400)+' UNIQUE_BETA_SOURCE '+('delta epsilon '*400),
        question='Which evidence is visible?',task_requirement='Only give the final answer.',
        window_tokens=1024,max_output_tokens=128,max_calls=30,**changes)

async def test_all_text_order_coverage_and_only_last_cu_enters_manager():
    calls=[]
    async def raw(stage,messages,parameters):
        calls.append(dict(stage=stage,messages=messages,parameters=parameters))
        return dict(raw='FINAL_ONLY_CU_'+str(len(calls)) if stage.startswith('worker.') else 'Final answer')
    result=await execute('chain_of_agents',request(),raw)
    chunks=result['chunks']
    assert len(chunks)>2 and ''.join(c['text'] for c in chunks)==request()['text']
    assert chunks[0]['start']==0 and chunks[-1]['end']==len(request()['text'])
    assert all(a['end']==b['start'] for a,b in zip(chunks,chunks[1:]))
    assert all(c['proxy_input_tokens']+128<=1024 for c in result['requests'])
    assert 'FINAL_ONLY_CU_1' in calls[1]['messages'][-1]['content']
    manager=calls[-1]['messages'][-1]['content']
    assert ('FINAL_ONLY_CU_'+str(len(chunks))) in manager
    assert 'FINAL_ONLY_CU_1\n' not in manager and 'UNIQUE_ALPHA_SOURCE' not in manager
    assert result['author_code_executed'] is False and result['source_kind']=='paper_algorithm_reimplementation'
    assert len(calls)==len(chunks)+1 and all(c['parameters']=={'temperature':0,'max_tokens':128} for c in calls)

async def test_unicode_is_not_lost_at_token_chunk_boundaries():
    text=('甲乙中文🙂🧪 ' *800)+'终点'
    async def raw(*a):return dict(raw='source summary')
    payload=request();payload['text']=text
    result=await execute('chain_of_agents',payload,raw)
    assert ''.join(c['text'] for c in result['chunks'])==text
    assert all(c['text']==text[c['start']:c['end']] for c in result['chunks'])

async def test_insufficient_call_budget_stops_before_first_model_request():
    calls=[]
    async def raw(*args):calls.append(args);return dict(raw='should not run')
    payload=request();payload['max_calls']=1
    with pytest.raises(ValueError,match='before inference'):
        await execute('chain_of_agents',payload,raw)
    assert calls==[]

async def test_oversized_cu_is_retained_as_failure_without_truncation_or_retry():
    calls=[]
    async def raw(*args):calls.append(args);return dict(raw='oversized '*4000)
    with pytest.raises(ValueError,match='window exceeded'):
        await execute('chain_of_agents',request(),raw)
    assert len(calls)==1

async def test_case_main_chain_uses_raw_coa_and_literal_anchors():
    source=dict(id='s1',text='甲称已付款，乙称待核对。',citation_units=citation_units('甲称已付款，乙称待核对。'))
    output=dict(elements=[],**demo_analysis({'sources':[source]}));calls=[];artifacts=[]
    async def raw(stage,messages,parameters):
        calls.append(dict(stage=stage,messages=messages))
        return dict(raw=json.dumps(output,ensure_ascii=False) if stage=='manager' else '甲称已付款，乙称待核对；来源s1，完整字符锚点见输入。')
    async def generic(*args):raise AssertionError('Old generic character-based workers must not execute')
    async def record(name,result):artifacts.append(result)
    result=await run_method('E14',dict(goal='核对陈述',sources=[source]),[source],generic,generic,SYSTEM_POLICY,lambda:output,
        dict(max_model_calls=10),raw_call=raw,author_record=record)
    validate_output(result,dict(sources=[source]))
    assert [x['stage'] for x in calls]==['worker.0000','manager']
    assert 'source_ref_id' in calls[0]['messages'][-1]['content']
    assert 'citation_units' not in calls[-1]['messages'][-1]['content']
    assert artifacts[0]['author_code_executed'] is False

async def test_predicted_kie_text_vqa_and_pixel_rejection():
    from screenshotlegal.method_reproductions.e14_chain_of_agents import run_task
    calls=[]
    async def raw(stage,messages,parameters):calls.append(stage);return dict(raw='{"answer":"yes","evidence":[]}' if stage=='manager' else 'KIE shows a message')
    task=dict(track='vqa_predicted_text',question='是否可见消息？',upstream_prediction=dict(conversation=[dict(content='hello')]))
    result=await run_task([dict(role='system',content='返回JSON answer和evidence'),dict(role='user',content=json.dumps(task))],raw)
    assert result['output']['answer']=='yes' and len(calls)==2
    with pytest.raises(ValueError,match='text-only'):
        await run_task([dict(role='system',content='JSON'),dict(role='user',content=[dict(type='image_url',image_url={'url':'data:image/png;base64,AA=='})])],raw)


def test_case_http_dispatch_and_export_has_paper_fidelity(accounts):
    import time
    from test_agent_experiments import create_case,payload
    _,_,client,_=accounts
    cid,doc=create_case(client,'甲称已经付款，乙称尚待核对。')
    response=client.post('/v1/evaluation/agent-runs',json=payload(cid,doc,method_ids=['E14']))
    assert response.status_code==201,response.text
    rid=response.json()['run_ids'][0]
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        result=client.get('/v1/evaluation/agent-runs/'+rid).json()
        if result['run']['status'] not in ['queued','running']:break
        time.sleep(.1)
    assert result['run']['status']=='completed',result['run'].get('error')
    artifact=result['author_artifacts'][0]['execution']
    assert artifact['source_kind']=='paper_algorithm_reimplementation' and artifact['author_code_executed'] is False
    assert result['run']['scoring_status']=='unscored_demo'
    assert client.get('/v1/evaluation/agent-runs/'+rid+'/export').status_code==200

async def test_benchmark_dispatch_preserves_frozen_text_and_effective_output_cap(lab):
    from test_benchmark_pipeline import setup
    from test_benchmark_migration import prompt
    from test_research_products import drain
    pipeline,p,calls,benchmark=setup(lab)
    row=pipeline.create('alice',p);await drain(lab)
    attempt=next(a for a in lab.store.list('benchmark.attempt','alice') if a['pipeline_id']==row['id'] and a['task_family']=='kie.extract')
    vp=prompt(benchmark,'vqa')
    payload=dict(dataset_id=p['dataset_id'],name='CoA benchmark dispatch',task_ids=['global'],track='vqa_predicted_text',mode='development_reference',
        release_id=None,model_id='local-fixture',prompt_id=vp['id'],method_id='E14',method_attempts=2,method_max_output_tokens=6144,max_calls=8,
        iou_threshold=.6,upstream_attempt_id=attempt['id'],idempotency_key='coa-benchmark')
    observed=[]
    async def actual_transport(owner,model,messages,purpose,request_id):
        observed.append(dict(model=model,messages=messages))
        return dict(raw='{"answer":"is_evidence","evidence":[]}' if request_id.endswith(':manager') else 'The KIE prediction says Visible text.',
            usage=dict(prompt_tokens=100,completion_tokens=20,total_tokens=120),latency_ms=1,cost_estimate=0.,cost_currency='CNY',demo=False)
    lab.gateway._call=actual_transport
    run=benchmark.create_run('alice',payload);await drain(lab)
    result=benchmark.results('alice',run['id'])
    assert result['run']['status']=='completed',result['attempts']
    assert len(observed)==2 and all(r['model']['parameters']['max_tokens']==2048 for r in observed)
    assert all(r['model']['parameters']['temperature']==0 for r in observed)
    assert 'Visible text' in observed[0]['messages'][-1]['content']
    assert 'is_evidence' in observed[0]['messages'][-1]['content']
    assert 'not_evidence' in observed[0]['messages'][-1]['content']
    assert 'LEGACY_PRIVATE_ANSWER' not in json.dumps(observed)
    assert result['run']['method']['source_kind']=='paper_algorithm_reimplementation'
    assert result['run']['method']['author_code_executed'] is False

async def test_query_free_summary_preserves_non_query_algorithm_contract():
    seen=[]
    async def raw(stage,messages,parameters):
        seen.append(dict(stage=stage,messages=messages))
        return dict(raw='Cumulative summary' if stage.startswith('worker.') else 'Final document summary')
    payload=dict(text='Visible document without a question.',question='',query_based=False,task_requirement='Summarize the complete document.',window_tokens=8192,max_output_tokens=1024,max_calls=3)
    result=await execute('chain_of_agents',payload,raw)
    assert result['output']=='Final document summary'
    assert [x['stage'] for x in seen]==['worker.0000','manager']
    assert 'Question:' not in seen[0]['messages'][-1]['content'] and 'Question:' not in seen[1]['messages'][-1]['content']
    assert 'Visible document' not in seen[1]['messages'][-1]['content']
    assert 'Cumulative summary' in seen[1]['messages'][-1]['content']
