"""Exercise author code, durable step accounting and existing frozen image inputs.

Transport responses are deterministic fixtures; no paper quality claims or paid calls.
"""
import copy
import json
import pytest
from test_research_products import lab,drain
from test_accounts_ingestion import accounts
from test_benchmark_migration import prompt,kie,message
from benchmark_fixtures import seed
from screenshotlegal.research.benchmark import Benchmark
from screenshotlegal.research.gateway import ModelFailure


def setup(lab,task_id='kie',max_calls=4,raw=None):
    dataset,tasks=seed(lab.store)
    b=Benchmark(lab.store,lab.gateway);lab.worker.benchmark=b
    p=prompt(b,'kie' if task_id=='kie' else 'vqa')
    calls=[]
    lab.gateway.freeze=lambda *a,**kw:dict(id='fixed',config_id='local-fixture',name='local',parameters={},billing=dict(input_token_price=0,output_token_price=0,currency='CNY'))
    async def response(owner,model,messages,purpose,request_id):
        calls.append(copy.deepcopy(messages))
        n=len(calls)
        result=raw(n) if raw else ('Scores:\nIssues: 保留原文及未知\nTotal score: 20/25' if n%2==0 else json.dumps(kie([dict(message([10,10,110,90]),content='System: User: Response: #原文')])) if task_id=='kie' else 'Scores:\nIssues: 保留未知\nTotal score: 20/25' if n%2==0 else '{"answer":"is_evidence","evidence":["visible"]}')
        return dict(raw=result,usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),latency_ms=1,cost_estimate=0,cost_currency='CNY',demo=False,response_model='local-fixture')
    lab.gateway._call=response
    payload=dict(dataset_id=dataset['id'],name='作者控制器适配验证',task_ids=[task_id],track='kie_image' if task_id=='kie' else 'vqa_image_full',mode='development_reference',model_id='local-fixture',prompt_id=p['id'],method_id='E05',method_attempts=2,method_max_output_tokens=6144,max_calls=max_calls,iou_threshold=.6,idempotency_key='author')
    return b,payload,calls


@pytest.mark.parametrize('task_id',['kie','vqa'])
async def test_product_executes_author_controller_with_frozen_images(lab,task_id):
    b,p,calls=setup(lab,task_id)
    run=b.create_run('alice',p)
    await drain(lab)
    result=b.results('alice',run['id'])
    assert result['run']['status']=='completed'
    assert result['run']['new_model_calls']==4 and len(calls)==4
    assert [s['stage'] for s in result['method_steps']]==['feedback.0','feedback.1','init','revise.1'] or {s['stage'] for s in result['method_steps']}=={'init','feedback.0','revise.1','feedback.1'}
    assert all(s['response']['raw'] for s in result['method_steps'])
    assert all('LEGACY_PRIVATE_ANSWER' not in json.dumps(c) and 'legacy_raw' not in json.dumps(c) for c in calls)
    images=[[p for p in c[1]['content'] if p['type']=='image_url'] for c in calls]
    assert all(image==images[0] and len(image)==1 for image in images)
    attempt=result['attempts'][0]
    assert attempt['response']['author_execution']['controller_source']=='src/responsegen/run.py:iterative_response'
    assert attempt['response']['author_execution']['original_benchmark_reproduced'] is False
    assert attempt['response']['usage']['prompt_tokens']==40
    if task_id=='kie':assert attempt['parsed']['conversation'][0]['content']=='System: User: Response: #原文'
    else:assert attempt['parsed']['answer']=='is_evidence'
    # A repeated worker execution must use the saved result and make no new call.
    await drain(lab)
    assert len(calls)==4


def test_rejects_insufficient_actual_step_budget_before_model(lab):
    b,p,calls=setup(lab,max_calls=3)
    with pytest.raises(ValueError,match='步骤'):b.create_run('alice',p)
    assert not calls and not lab.store.list('evaluation.request','alice')


async def test_invalid_author_output_keeps_response_and_stops_without_retry(lab):
    b,p,calls=setup(lab,raw=lambda n:'invalid JSON')
    run=b.create_run('alice',p);await drain(lab)
    result=b.results('alice',run['id'])
    assert result['run']['status']=='failed' and result['run']['new_model_calls']==1
    assert len(calls)==1 and result['method_steps'][0]['response']['raw']=='invalid JSON'
    assert result['attempts'][0]['status']=='failed'


async def test_missing_usage_stops_after_saved_response(lab):
    b,p,calls=setup(lab)
    original=lab.gateway._call
    async def no_usage(*args):
        result=await original(*args);result['usage']=None;return result
    lab.gateway._call=no_usage
    run=b.create_run('alice',p);await drain(lab)
    result=b.results('alice',run['id'])
    assert result['run']['new_model_calls']==1 and len(calls)==1
    assert result['attempts'][0]['status']=='failed'
    assert result['method_steps'][0]['response']['usage'] is None


@pytest.mark.parametrize('task_id',['kie','vqa'])
async def test_react_runs_original_notebook_with_real_pixel_crop(lab,task_id):
    b,p,calls=setup(lab,task_id,max_calls=14)
    p['method_id']='E01'
    async def response(owner,model,messages,purpose,request_id):
        calls.append(copy.deepcopy(messages));n=len(calls)
        value=kie([message([10,10,110,90])]) if task_id=='kie' else dict(answer='is_evidence',evidence=['visible'])
        raw='核对局部\nAction 1: Lookup[10,10,110,90]' if n==1 else '整理答案\nAction 2: Finish['+json.dumps(value,ensure_ascii=False)+']'
        return dict(raw=raw,usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),latency_ms=1,cost_estimate=0,cost_currency='CNY',demo=False,response_model='local-fixture')
    lab.gateway._call=response
    run=b.create_run('alice',p);await drain(lab)
    result=b.results('alice',run['id'])
    assert result['run']['status']=='completed' and result['run']['new_model_calls']==2
    assert result['attempts'][0]['response']['author_execution']['controller_source']=='hotpotqa.ipynb:webthink'
    assert len(calls)==2 and len(result['method_tools'])==1
    tool=result['method_tools'][0]
    assert tool['result']['source_bbox_xyxy']==[10,10,110,90]
    assert tool['result']['source_sha256'] and tool['result']['crop_sha256']
    first_images=[p for p in calls[0][1]['content'] if p['type']=='image_url']
    second_images=[p for p in calls[1][1]['content'] if p['type']=='image_url']
    assert len(first_images)==1 and len(second_images)==2 and first_images[0]==second_images[0]
    import base64,io
    from PIL import Image
    with Image.open(io.BytesIO(base64.b64decode(second_images[1]['image_url']['url'].split(',')[1]))) as crop:
        assert crop.size==(100,80)
    assert all('LEGACY_PRIVATE_ANSWER' not in json.dumps(c) for c in calls)


async def test_react_rejects_crop_outside_frozen_original(lab):
    b,p,calls=setup(lab,max_calls=14,raw=lambda n:'读取局部\nAction 1: Lookup[-1,0,50,50]')
    p['method_id']='E01'
    run=b.create_run('alice',p);await drain(lab)
    result=b.results('alice',run['id'])
    assert result['run']['status']=='failed' and result['run']['new_model_calls']==1
    assert len(calls)==1 and not result['method_tools']


@pytest.mark.parametrize('after_response',[1,4,'parent'])
async def test_author_recovery_replays_known_responses_without_duplicate_requests(lab,after_response):
    b,p,calls=setup(lab);run=b.create_run('alice',p);job=lab.store.claim();seen=0
    class SimulatedProcessExit(BaseException):pass
    async def alive():pass
    async def checkpoint(key,value,phase):
        nonlocal seen
        with lab.store.tx() as db:
            current=lab.store.job(job['id'],'alice',db);current['phase']=phase
            lab.store.save_job(db,current,job['lease_token'])
        if key.startswith('method-response:'):
            seen+=1
            if seen==after_response:raise SimulatedProcessExit()
        if key.startswith('response:') and after_response=='parent':raise SimulatedProcessExit()
    with pytest.raises(SimulatedProcessExit):await b.execute(None,job,checkpoint,alive)
    assert len(calls)==(4 if after_response=='parent' else after_response)
    with lab.store.tx() as db:db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(job['id'],))
    recovered=lab.store.claim();assert recovered['status']=='running'
    await lab.worker.execute(recovered)
    result=b.results('alice',run['id'])
    assert result['run']['status']=='completed' and len(calls)==4
    assert len(result['method_steps'])==4 and result['run']['new_model_calls']==4
    assert result['attempts'][0]['parsed']['conversation'][0]['content']=='System: User: Response: #原文'


async def test_author_unknown_inflight_never_resends_and_counts_durable_request(lab):
    import asyncio
    b,p,calls=setup(lab)
    async def interrupted(*args):
        calls.append(args[2]);raise asyncio.CancelledError()
    lab.gateway._call=interrupted
    run=b.create_run('alice',p);job=lab.store.claim()
    with pytest.raises(asyncio.CancelledError):await lab.worker.execute(job)
    with lab.store.tx() as db:db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(job['id'],))
    unknown=lab.store.claim();assert unknown['status']=='unknown'
    await lab.worker.execute(unknown)
    result=b.results('alice',run['id'])
    assert result['run']['status']=='unknown' and result['attempts'][0]['status']=='unknown'
    assert result['run']['new_model_calls']==result['report']['model_calls']==1
    assert len(calls)==1 and result['method_steps'][0]['status']=='unknown'
