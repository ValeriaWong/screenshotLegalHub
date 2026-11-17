"""GraphRAG author-code execution and product acceptance; zero supplier calls."""
import json,time
import pytest
from test_accounts_ingestion import accounts
from test_research_products import lab,drain
from screenshotlegal.method_reproductions.paper_bridge import execute
from screenshotlegal.method_reproductions.graphrag_bridge import demo_reply

@pytest.mark.asyncio
async def test_native_original_context_and_scored_map_reduce_are_executed():
    seen=[]
    async def transport(stage,messages,parameters):
        seen.append(dict(stage=stage,messages=messages,parameters=parameters))
        if stage.startswith('query.map.'):
            return dict(raw=json.dumps(dict(points=[dict(description='LOW',score=10),dict(description='HIGH',score=90),dict(description='ZERO_MUST_BE_FILTERED',score=0)])))
        prompt=messages[0]['content']
        assert prompt.index('HIGH')<prompt.index('LOW') and 'ZERO_MUST_BE_FILTERED' not in prompt
        return dict(raw='native fixture output')
    request=dict(mode='native_query',question='What is the major conflict in this story and who are the protagonist and antagonist?')
    result=await execute('graphrag',request,transport)
    assert result['lineage']['table_rows']==dict(nodes=434,entities=217,reports=6)
    assert result['lineage']['selected_reports']==5 and result['lineage']['selected_entities']==217
    assert result['lineage']['native_index_regenerated'] is False
    assert [r['stage'] for r in seen]==['query.map.0000','query.reduce.0001']
    assert seen[0]['parameters']['response_format']==dict(type='json_object')
    assert result['query']['positive_map_points']==2 and result['author_code_executed']
    assert result['neural_modules_loaded']==[] and not result['original_complete_benchmark']

@pytest.mark.asyncio
async def test_complete_author_index_then_global_search_then_separate_case_projection():
    from screenshotlegal.method_reproductions import run_method
    from screenshotlegal.experiments.engine import SYSTEM_POLICY,visible_input,validate_output
    source=dict(id='s',text='甲😀称已付款，乙称待核对。')
    frozen=dict(case_title='test',goal='整理陈述及未知',sources=[source],legal_corpus=[])
    output=dict(summary='仅记录当事人陈述',facts=[dict(id='f',statement='材料记载甲称已付款，乙称待核对',citations=[dict(source_ref_id='s',quote=source['text'],start=0,end=len(source['text']))])])
    seen=[];artifacts=[]
    async def raw(stage,messages,params):
        seen.append(stage);return dict(raw=demo_reply(stage,messages,output),demo=True)
    async def forbidden(*a):raise AssertionError('generic prototype path must not execute')
    async def artifact(name,result):artifacts.append(result)
    result=await run_method('E24',visible_input(frozen,'E24'),[source],forbidden,forbidden,SYSTEM_POLICY,lambda:{},dict(max_model_calls=40),raw_call=raw,author_record=artifact)
    assert validate_output(result,frozen)['facts'][0]['citations'][0]['quote']==source['text']
    record=artifacts[0];workflows={w['workflow'] for w in record['indexing']['workflows']}
    assert {'create_base_text_units','create_base_extracted_entities','create_summarized_entities','create_base_entity_graph','create_final_community_reports'}<=workflows
    assert len(workflows)==14 and record['indexing']['selected_entities']==2 and record['indexing']['selected_reports']==1
    assert record['product_projection_separate'] and seen[-1]=='product_projection'
    assert not record['text_embeddings_computed'] and not record['graph_embeddings_computed']
    assert record['neural_modules_loaded']==[] and record['observations']

@pytest.mark.asyncio
async def test_pixel_input_is_rejected_before_any_call():
    from screenshotlegal.method_reproductions.r04_graphrag import run_task
    async def forbidden(*a):raise AssertionError('no model calls')
    with pytest.raises(ValueError,match='text-only'):
        await run_task([dict(role='user',content=[dict(type='image_url')])],forbidden)

def test_benchmark_and_case_catalog_have_real_graph_stage_and_text_budget():
    from screenshotlegal.research.benchmark_methods import specification
    from screenshotlegal.experiments.registry import CandidateRegistry,call_ceiling
    result=specification('E24')
    assert result['name']=='r04_graphrag' and result['calls_per_task']==40 and result['dynamic_call_budget']
    assert call_ceiling('E24',dict(max_model_calls=17),{},[])==17
    method=CandidateRegistry().method('E24')
    assert not method['requires_matterpack'] and 'author_leiden_communities' in method['steps']
    assert method['original_paper_reproduced'] is False

def test_case_http_executes_and_exports_graph_workflows_and_budget(accounts):
    from test_agent_experiments import create_case,payload
    _,_,client,bob=accounts
    cid,doc=create_case(client,'甲说已付款。乙说未核实。')
    p=payload(cid,doc,method_ids=['E24'],budget=dict(max_model_calls=30,max_wall_time_s=90,max_input_tokens=1000000,max_output_tokens=100000,max_output_per_call=4096))
    response=client.post('/v1/evaluation/agent-runs',json=p)
    assert response.status_code==201,response.text
    rid=response.json()['run_ids'][0];deadline=time.monotonic()+75
    while time.monotonic()<deadline:
        result=client.get('/v1/evaluation/agent-runs/'+rid).json()
        if result['run']['status'] not in ['queued','running']:break
        time.sleep(.1)
    assert result['run']['status']=='completed',result['run'].get('error')
    assert result['run']['scoring_status']=='unscored_demo'
    execution=result['author_artifacts'][0]['execution']
    assert len(execution['indexing']['workflows'])==14 and execution['product_projection_separate']
    assert result['reproduction_name']=='r04_graphrag'
    steps={r['stage']:r for r in result['steps']}
    assert steps['author.query.map.0000']['model_parameters']['max_tokens']==1000
    assert steps['author.query.map.0000']['model_parameters']['response_format']==dict(type='json_object')
    assert steps['author.query.reduce.0001']['model_parameters']['max_tokens']==2000
    assert bob.get('/v1/evaluation/agent-runs/'+rid).status_code==404
    assert client.get('/v1/evaluation/agent-runs/'+rid+'/export').status_code==200

async def test_benchmark_freezes_upstream_text_and_records_every_author_phase(lab):
    from test_benchmark_pipeline import setup
    from test_benchmark_migration import prompt
    pipeline,p,_,benchmark=setup(lab);row=pipeline.create('alice',p);await drain(lab)
    upstream=next(a for a in lab.store.list('benchmark.attempt','alice') if a.get('pipeline_id')==row['id'] and a['task_family']=='kie.extract')
    seen=[]
    async def transport(owner,model,messages,purpose,request_id):
        seen.append(dict(model=model,messages=messages))
        raw=demo_reply(request_id.rsplit(':',1)[1],messages,dict(answer='is_evidence',evidence=['frozen input']))
        return dict(raw=raw,usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),latency_ms=1,cost_estimate=0,cost_currency='CNY',demo=False)
    lab.gateway._call=transport
    vp=prompt(benchmark,'vqa')
    payload=dict(dataset_id=p['dataset_id'],name='GraphRAG author pipeline',task_ids=['global'],track='vqa_predicted_text',mode='development_reference',model_id='local-fixture',prompt_id=vp['id'],method_id='E24',method_attempts=2,method_max_output_tokens=6144,max_calls=40,iou_threshold=.6,upstream_attempt_id=upstream['id'],idempotency_key='graphrag')
    run=benchmark.create_run('alice',payload);await drain(lab);result=benchmark.results('alice',run['id'])
    assert result['run']['status']=='completed',result['attempts']
    assert result['attempts'][0]['parsed']['answer']=='is_evidence'
    execution=result['attempts'][0]['response']['author_execution']
    assert len(execution['indexing']['workflows'])==14 and execution['author_code_executed']
    assert len(result['method_steps'])==len(seen) and len(result['method_tools'])>=15
    assert 'LEGACY_PRIVATE_ANSWER' not in json.dumps(seen)
    assert all(isinstance(m['content'],str) for r in seen for m in r['messages'])
    await drain(lab)
    assert len(result['method_steps'])==len(seen)

@pytest.mark.asyncio
async def test_invalid_community_json_does_not_trigger_an_automatic_paid_reformat():
    seen=[]
    async def raw(stage,messages,parameters):
        seen.append(stage)
        if '"rating"' in messages[-1]['content'] and '"findings"' in messages[-1]['content']:return dict(raw='not JSON')
        return dict(raw=demo_reply(stage,messages,{}))
    request=dict(mode='product',documents=[dict(id='s',text='甲称已付款，乙称待核对。')],question='整理陈述')
    with pytest.raises(ValueError,match='Original index workflow failed'):
        await execute('graphrag',request,raw)
    assert seen==['index.0000','index.0001','index.0002']
