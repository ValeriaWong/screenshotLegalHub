"""LegalBench product bindings and actual HTTP offline dispatch, zero paid calls."""
import pytest,json
from test_accounts_ingestion import accounts
from test_research_products import lab
from test_benchmark_migration import kie,message
from screenshotlegal.research.legalbench_scoring import product

async def test_global_categorical_original_normalized_metric_and_missing_reference():
    task=dict(task_family='vqa.categorical',answer_kind='categorical',task_id='q',allowed_values=['yes','no'],input={})
    result=await product(task,{'answer':' YES. '},'yes')
    assert result['score']==1 and result['model_requests']==0
    assert result['reference_classes_present']==1 and result['expected_labels']==['yes','no']
    assert result['expert_legal_accuracy'] is None
    assert (await product(task,{'answer':'other'},'yes'))['score']==0
    assert (await product(task,{'answer':'yes'},None))['status']=='unscored_missing_reference'
    assert (await product(dict(task,region_id='region'),{'answer':'yes'},'yes'))['status']=='unsupported_task'

async def test_kie_only_compares_matched_text_and_preserves_extra_message_penalty():
    task=dict(task_id='kie-fixture',task_family='kie.extract',asset=dict(width=200,height=160))
    target=kie([message([10,10,110,90])]);raw=kie([message([10,10,110,90]),message([130,100,150,120])])
    result=await product(task,raw,target)
    assert result['score']==1 and result['geometry_match']['fp']==1
    assert len(result['bindings'])==2
    assert result['geometry_match']['f1']==pytest.approx(2/3)
    assert (await product(task,raw,None))['status']=='unscored_missing_reference'

def test_http_scores_are_owned_idempotent_and_exported_with_original_primary(accounts):
    _,_,alice,bob=accounts;store=alice.app.state.research['store']
    from screenshotlegal.research.benchmark import Benchmark
    from screenshotlegal.research.contracts import digest
    from benchmark_fixtures import seed
    dataset,tasks=seed(store)
    task=dict(tasks[0],task_family='vqa.categorical',answer_kind='categorical',region_id=None,target='yes',allowed_values=['yes','no'],input={'question':'是否为对话？'})
    run=dict(id='legalbench-run',dataset_id=dataset['id'],tasks=[task],mode='development_reference',scorer_config={'threshold':.6},model={'config_id':'frozen-test'},method={'id':'E00'},new_model_calls=0,status='completed')
    attempt=dict(id='legalbench-attempt',run_id=run['id'],dataset_id=dataset['id'],task_id=task['task_id'],status='completed',input_hash=digest(task['input']),response={'raw':'{"answer":"yes"}','demo':False})
    with store.tx() as db:
        store.put('benchmark.run',run,'alice',db);store.put('benchmark.attempt',attempt,'alice',db)
        primary=Benchmark(store).score_attempt('alice',run,task,attempt,db)
    url='/v1/evaluation/benchmark-attempts/'+attempt['id']+'/legalbench-score'
    result=alice.post(url,json={'idempotency_key':'offline'})
    assert result.status_code==201,result.text
    row=result.json();assert row['method']=='b04_legalbench' and row['result']['score']==1
    assert row['result']['model_requests']==0 and row['target_snapshot']=='yes'
    assert alice.post(url,json={'idempotency_key':'offline'}).json()['id']==row['id']
    assert bob.post(url,json={'idempotency_key':'foreign'}).status_code==404
    assert store.get('benchmark.score',primary['id'],'alice')==primary
    with store.tx() as db:
        store.put('benchmark.ragchecker_score',dict(row,id='fixture-rag-supplement',method='b15_ragchecker',paper_id='B15',result=dict(status='fixture',score=None)), 'alice',db)
    exported=alice.get('/v1/evaluation/benchmark-runs/'+run['id']+'/export')
    assert exported.status_code==200 and exported.json()['supplemental_scores'][0]['method']=='b04_legalbench'
    assert {s['method'] for s in exported.json()['supplemental_scores']}=={'b04_legalbench','b15_ragchecker'}
    assert not store.list('evaluation.request','alice')
    assert url.replace(attempt['id'],'{id}') in alice.get('/openapi.json').json()['paths']

async def test_pipeline_offline_metric_uses_current_scoreset_and_is_exported(lab):
    from test_benchmark_pipeline import setup
    from test_research_products import drain
    pipeline,p,_,benchmark=setup(lab)
    row=pipeline.create('alice',p);await drain(lab)
    node=next(n for n in pipeline.detail('alice',row['id'])['items'] if n['variant']=='full_image')
    result=await benchmark.legalbench_score('alice',node['attempt_id'],{'idempotency_key':'pipeline'})
    assert result['pipeline_id']==row['id'] and result['result']['model_requests']==0
    assert result['primary_score_id'].startswith(node['id']+':')
    assert pipeline.export('alice',row['id'])['supplemental_scores'][0]['id']==result['id']
    assert pipeline.node_detail('alice',row['id'],node['id'])['supplemental_scores'][0]['id']==result['id']
