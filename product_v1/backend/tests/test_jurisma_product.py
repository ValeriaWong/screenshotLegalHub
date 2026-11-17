"""E18 isolated product acceptance. Deterministic fixtures, zero supplier calls."""
import json
from test_accounts_ingestion import accounts
from test_research_products import lab,drain
from screenshotlegal.method_reproductions.jurisma_bridge import demo_reply

def test_case_http_uses_inference_and_exports_method_named_artifact(accounts):
    from test_agent_experiments import create_case,payload,wait_run
    _,_,client,bob=accounts
    cid,doc=create_case(client,'甲称已付款，乙称待核对。')
    client.put('/v1/cases/'+cid+'/matter-selection',json=dict(matter_pack_id='cn.civil.private_lending'))
    p=payload(cid,doc,method_ids=['E18'],allow_draft_matter=True,budget=dict(max_model_calls=29,max_wall_time_s=60))
    response=client.post('/v1/evaluation/agent-runs',json=p)
    assert response.status_code==201,response.text
    rid=response.json()['run_ids'][0];result=wait_run(client,rid)
    assert result['run']['status']=='completed',result['run'].get('error')
    assert result['run']['usage']['model_calls']==5 and result['run']['scoring_status']=='unscored_demo'
    artifact=result['author_artifacts'][0]
    assert artifact['reproduction_name']=='e18_jurisma'
    execution=artifact['execution']
    assert execution['projection_is_product_adaptation'] and not execution['training_reproduced']
    assert execution['requests'][-1]['stage']=='content_check'
    assert not execution['original_complete_benchmark']
    assert result['run']['output']['facts'][0]['citations']
    assert bob.get('/v1/evaluation/agent-runs/'+rid).status_code==404
    export=client.get('/v1/evaluation/agent-runs/'+rid+'/export')
    assert export.status_code==200 and b'e18_jurisma' in export.content

async def test_benchmark_freezes_kie_text_without_gold_and_saves_all_steps(lab):
    from test_benchmark_pipeline import setup
    from test_benchmark_migration import prompt
    pipeline,p,_,benchmark=setup(lab)
    row=pipeline.create('alice',p);await drain(lab)
    upstream=next(a for a in lab.store.list('benchmark.attempt','alice') if a.get('pipeline_id')==row['id'] and a['task_family']=='kie.extract')
    seen=[]
    async def transport(owner,model,messages,purpose,request_id):
        seen.append(messages)
        return dict(raw=demo_reply(request_id.rsplit(':',1)[1],dict(answer='is_evidence',evidence=['frozen visible text'])),usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),latency_ms=1,cost_estimate=0,cost_currency='CNY',demo=False)
    lab.gateway._call=transport
    vp=prompt(benchmark,'vqa')
    payload=dict(dataset_id=p['dataset_id'],name='JurisMA inference',task_ids=['global'],track='vqa_predicted_text',mode='development_reference',model_id='local-fixture',prompt_id=vp['id'],method_id='E18',method_attempts=2,method_max_output_tokens=6144,max_calls=29,iou_threshold=.6,upstream_attempt_id=upstream['id'],idempotency_key='jurisma')
    result=benchmark.create_run('alice',payload);await drain(lab)
    result=benchmark.results('alice',result['id'])
    assert result['run']['status']=='completed',result['attempts']
    assert result['run']['new_model_calls']==5
    assert result['attempts'][0]['parsed']['answer']=='is_evidence'
    assert len(result['method_steps'])==5
    assert {t['action'] for t in result['method_tools']}=={'jurisma.element_graph','jurisma.iteration'}
    assert not result['attempts'][0]['response']['author_execution']['training_reproduced']
    assert 'LEGACY_PRIVATE_ANSWER' not in json.dumps(seen)
    assert all(isinstance(m['content'],str) for call in seen for m in call)
    await drain(lab)
    assert len(seen)==5
