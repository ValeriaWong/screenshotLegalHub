"""Author LawBench scorer/CLI and product bindings. Scripted fixtures use zero API calls."""
import json
import pytest
from test_accounts_ingestion import accounts
from test_research_products import lab
from test_benchmark_migration import kie,message
from screenshotlegal.research.lawbench_scoring import official,product

async def test_original_cli_and_unmodified_typo_are_retained():
    output=await official({'2-5':[dict(origin_prompt='原阅读任务',prediction='甲乙',refr='回答:甲丙')],
        '2-6':[dict(origin_prompt='原实体任务',prediction='受害人:严某某',refr='受害人:严某某')]})
    assert output['raw_scores']['2-5']['score']==.5
    assert 'anstention_rate' in output['raw_scores']['2-6']
    assert 'abstention_rate' not in output['raw_scores']['2-6']
    assert '2-5,submitted_predictions,0.5,0' in output['official_cli']['csv']
    assert output['model_requests']==0 and output['local_model_inference'] is False

async def test_deferred_local_ltp_task_is_rejected():
    with pytest.raises(ValueError,match='locally deferred'):
        await official({'2-1':[dict(origin_prompt='句子：甲',prediction='乙',refr='丙')]})

async def test_vqa_uses_official_text_metric_without_scoring_legal_analysis():
    task=dict(task_family='vqa.text',answer_kind='text',task_id='q1',input={'question':'原文是什么？'})
    result=await product(task,{'answer':'甲乙'},'甲丙')
    assert result['status']=='scored' and result['score']==.5
    assert result['original_scorer_input']['2-5'][0]['prediction']=='甲乙'
    assert result['legal_accuracy'] is None
    for kind in ('open_text','amount','identity','categorical','set'):
        result=await product(dict(task,answer_kind=kind),{'answer':'甲乙'},'甲丙')
        assert result['status']=='unsupported_task' and result['score'] is None
    assert (await product(task,{'answer':'甲乙'},None))['status']=='unscored_missing_reference'


async def test_closed_global_vqa_maps_frozen_labels_and_keeps_invalid_abstention():
    task=dict(task_family='vqa.categorical',answer_kind='categorical',task_id='closed',input={'question':'是否为聊天记录？'},allowed_values=['not_chat','is_chat'])
    result=await product(task,{'answer':'is_chat'},'is_chat')
    assert result['metric']=='official_1-2_choice_accuracy' and result['score']==1
    assert result['bindings'][0]['label_to_option']=={'not_chat':'A','is_chat':'B'}
    assert result['original_scorer_input']['1-2'][0]['prediction']=='B'
    invalid=await product(task,{'answer':'B'},'is_chat')  # raw option is not a valid product label
    assert invalid['score']==0 and invalid['author_execution']['raw_scores']['1-2']['abstention_rate']==1

async def test_kie_geometry_is_separate_and_extra_messages_remain_penalized():
    task=dict(task_family='kie.extract',asset=dict(width=200,height=160))
    target=kie([message([10,10,110,90])])
    output=kie([message([10,10,110,90]),message([130,100,150,120])])
    result=await product(task,output,target)
    assert result['score']==1  # text only on matched fields
    assert result['geometry_match']['fp']==1 and result['geometry_match']['f1']==pytest.approx(2/3)
    assert len(result['bindings'])==2  # speaker + content; null fields excluded
    assert '2-6' not in result['original_scorer_input']
    assert (await product(task,kie([]),target))['status']=='unscored_no_comparable_fields'

async def test_native_selection_uses_original_prompts_and_hides_current_answers():
    from paper.author_reproductions.lawbench.adapter import native_inputs
    inputs=native_inputs()
    assert len(inputs['samples'])==38 and len(inputs['inventory'])==40
    assert all(s['index']==0 and s['task']!='2-1' for s in inputs['samples'])
    from pathlib import Path
    from screenshotlegal.research.lawbench_scoring import ROOT
    for s in inputs['samples']:
        row=json.loads((ROOT/s['input_path']).read_text(encoding='utf-8'))[0]
        assert s['messages']==[dict(role='user',content=row['instruction']+'\n'+row['question'])]
        assert s['reference_sent_to_model'] is False


def test_http_offline_scores_are_owned_idempotent_and_exported(accounts):
    _,_,alice,bob=accounts
    store=alice.app.state.research['store']
    from screenshotlegal.research.benchmark import Benchmark
    from screenshotlegal.research.contracts import digest
    from benchmark_fixtures import seed
    dataset,tasks=seed(store)
    task=dict(tasks[0],task_family='vqa.text',answer_kind='text',region_id=None,target='甲丙',input={'question':'可见文字是什么？'})
    run=dict(id='lawbench-run',dataset_id=dataset['id'],tasks=[task],mode='development_reference',scorer_config={'threshold':.6},
        model={'config_id':'frozen-test'},method={'id':'E00'},new_model_calls=0,status='completed')
    attempt=dict(id='lawbench-attempt',run_id=run['id'],dataset_id=dataset['id'],task_id=task['task_id'],status='completed',
        input_hash=digest(task['input']),response={'raw':json.dumps({'answer':'甲乙'},ensure_ascii=False),'demo':False})
    with store.tx() as db:
        store.put('benchmark.run',run,'alice',db)
        store.put('benchmark.attempt',attempt,'alice',db)
        Benchmark(store).score_attempt('alice',run,task,attempt,db)
    url='/v1/evaluation/benchmark-attempts/'+attempt['id']+'/lawbench-score'
    result=alice.post(url,json={'idempotency_key':'offline-supplement'})
    assert result.status_code==201,result.text
    row=result.json()
    assert row['result']['score']==.5 and row['result']['model_requests']==0
    assert alice.post(url,json={'idempotency_key':'offline-supplement'}).json()['id']==row['id']
    assert bob.post(url,json={'idempotency_key':'other-owner'}).status_code==404
    exported=alice.get('/v1/evaluation/benchmark-runs/'+run['id']+'/export')
    assert exported.status_code==200,exported.text
    assert exported.json()['supplemental_scores'][0]['method']=='b02_lawbench'
    assert store.list('evaluation.request','alice')==[]
    assert len(store.list('benchmark.score','alice'))==1  # primary score not overwritten

async def test_pipeline_uses_current_frozen_scoreset_and_exports_supplement(lab):
    from test_benchmark_pipeline import setup
    from test_research_products import drain
    pipeline,p,_,benchmark=setup(lab)
    row=pipeline.create('alice',p);await drain(lab)
    node=next(n for n in pipeline.detail('alice',row['id'])['items'] if n['variant']=='full_image')
    result=await benchmark.lawbench_score('alice',node['attempt_id'],{'idempotency_key':'pipeline-offline'})
    assert result['pipeline_id']==row['id'] and result['result']['model_requests']==0
    assert result['primary_score_id'].startswith(node['id']+':')
    assert pipeline.export('alice',row['id'])['supplemental_scores'][0]['id']==result['id']
    assert pipeline.node_detail('alice',row['id'],node['id'])['supplemental_scores'][0]['id']==result['id']
