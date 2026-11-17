import asyncio
import copy
import json
import pytest
from screenshotlegal.research.benchmark import Benchmark
from screenshotlegal.research.benchmark_pipeline import Pipeline, associate, NODE, KIND
from screenshotlegal.research import benchmark_scoring as scoring, audit
from screenshotlegal.research.contracts import digest, now
from screenshotlegal.research.benchmark_import import blob
from screenshotlegal.research.store import Conflict
from screenshotlegal.research.operations import Operations
from screenshotlegal.research.gateway import ModelFailure
from test_research_products import lab, drain
from test_accounts_ingestion import accounts
from test_benchmark_migration import prompt, kie, message, reviewed
from benchmark_fixtures import seed


def setup(lab, response=None):
    d,tasks=seed(lab.store)
    # A global task must remain independent of the image's KIE failure.
    all_tasks=copy.deepcopy(tasks)
    global_task=copy.deepcopy(tasks[0]);global_task.update(task_id='global',region_id=None,bbox_xyxy=None,question='Is this a conversation?')
    all_tasks.append(global_task)
    d=copy.deepcopy(d);d.update(id='benchmark.pipeline-fixture',counts=dict(d['counts'],vqa=3))
    for t in all_tasks:t['dataset_id']=d['id'];t['allowed_values']=['is_evidence','not_evidence']
    ref=blob(lab.store,json.dumps(all_tasks).encode());d.update(tasks=ref,image_files={'fixture.png':ref})
    with lab.store.tx() as db:lab.store.put('benchmark.dataset',d,'alice',db,immutable=True)
    b=Benchmark(lab.store,lab.gateway);pipeline=Pipeline(b);b.pipeline=pipeline;lab.worker.benchmark=b;lab.worker.pipeline=pipeline
    kp,vp=prompt(b,'kie'),prompt(b,'vqa');calls=[]
    lab.gateway.freeze=lambda *a,**kw:dict(id='fixed-model',config_id='local-fixture',name='local',parameters={},billing=dict(input_token_price=0,output_token_price=0,currency='CNY'))
    async def fake(owner,model,messages,purpose,request_id):
        calls.append(copy.deepcopy(messages))
        raw=(response(messages,len(calls)) if response else json.dumps(kie([message([10,10,110,90])]))) if len(calls)==1 else '{"answer":"is_evidence"}'
        return dict(raw=raw,usage=dict(prompt_tokens=10,completion_tokens=10),latency_ms=1,cost_estimate=0.,cost_currency='CNY',demo=False,request_id=request_id)
    lab.gateway._call=fake
    p=dict(dataset_id=d['id'],name='按图自动测试',task_ids=['vqa','open','global'],all_tasks=False,model_id='local-fixture',kie_prompt_id=kp['id'],vqa_prompt_id=vp['id'],mode='development_reference',release_id=None,max_calls=4,iou_threshold=.6,regional_controls=False,allow_unverified_assets=False,idempotency_key='pipeline')
    return pipeline,p,calls,b


async def test_full_pipeline_matched_input_plan_and_history(lab):
    pipeline,p,calls,b=setup(lab);preview=pipeline.preview('alice',p)
    assert preview['maximum_calls']==4 and not calls and lab.store.list('evaluation.request','alice')==[]
    row=pipeline.create('alice',p);assert pipeline.create('alice',p)['id']==row['id']
    with pytest.raises(Conflict):pipeline.create('alice',dict(p,name='conflict'))
    await drain(lab);detail=pipeline.detail('alice',row['id']);report=detail['report']
    assert detail['pipeline']['status']=='completed' and len(calls)==4
    assert report['conserved'] and report['vqa_planned']==3 and report['kie_images']==1
    assert report['association']['planned_regions']==1 and report['association']['matched_regions']==1 and report['association']['planned_attribute_questions']==2
    assert all(x['status']=='response_received' for x in detail['items'])
    for node in detail['items']:
        data=pipeline.node_detail('alice',row['id'],node['id'])
        assert 'LEGACY_PRIVATE_ANSWER' not in json.dumps(data['input']) and 'target' not in data['input']
        if node['variant']=='reference_guided_prediction':
            assert node['match']['prediction_id']==data['node']['prediction_id']
            assert data['input']['messages'][0]['content']=='Visible text' and 'images' not in data['input']
    assert any(g['pending_judgement']==1 for g in report['groups'] if g['answer_kind']=='open_text')
    assert report['cost']['call_reservations']==4 and report['cost']['complete']
    assert Operations(lab.store).resolve('alice',row['id'])['href'].endswith('pipeline='+row['id'])
    assert audit.query(lab.store,'alice',object_id=row['id'])['items']
    with pytest.raises(KeyError):pipeline.detail('bob',row['id'])


@pytest.mark.parametrize('messages,reason', [([], 'no_message'),([message([130,100,190,150])],'zero_overlap'),([message([10,10,50,40])],'below_threshold')])
async def test_low_iou_keeps_every_planned_question_and_global_runs(lab,messages,reason):
    pipeline,p,calls,_=setup(lab,lambda m,n:json.dumps(kie(messages)))
    row=pipeline.create('alice',p);await drain(lab);result=pipeline.detail('alice',row['id'])
    blocked=[n for n in result['items'] if n['variant']=='reference_guided_prediction']
    assert len(blocked)==2 and all(n['status']=='blocked_no_match' and n['reason']==reason for n in blocked)
    assert result['report']['planned_units']==4 and len(calls)==2
    assert any(n['variant']=='full_image' and n['status']=='response_received' for n in result['items'])
    assert len(lab.store.list('benchmark.match','alice'))==1  # one physical region, two questions


async def test_bad_kie_retains_errors_and_global_is_independent(lab):
    pipeline,p,calls,_=setup(lab,lambda m,n:json.dumps(kie([message([10,10,110,90]),message([-1,1,30,20])])))
    row=pipeline.create('alice',p);await drain(lab);result=pipeline.detail('alice',row['id'])
    assert len(calls)==2 and sum(n['status']=='blocked_upstream' for n in result['items'])==2
    pred=lab.store.list('benchmark.prediction','alice')[0]
    assert pred['validation_errors'][0]['message_index']==1 and not pred['eligible_for_dependency']


async def test_local_scorer_failure_does_not_reissue_request(lab,monkeypatch):
    pipeline,p,calls,_=setup(lab);row=pipeline.create('alice',p)
    original=pipeline._score
    def broken(*a,**k):raise RuntimeError('local scorer broken')
    monkeypatch.setattr(pipeline,'_score',broken)
    job=lab.store.claim();await lab.worker.execute(job)
    node=lab.store.get(NODE,job['payload']['node_id'],'alice')
    assert node['status']=='response_received' and node['local_error'] and len(calls)==1
    assert lab.store.get('benchmark.attempt',node['attempt_id'],'alice')['status']=='completed'
    monkeypatch.setattr(pipeline,'_score',original)
    # Finish independent work, then explicitly restore the local stage only.
    await drain(lab)
    before=len(calls);pipeline.resume_local('alice',row['id'],dict(node_ids=[node['id']],reason='修复本地评分器',idempotency_key='resume'))
    await drain(lab)
    assert len(calls)==before+2  # two newly unblocked VQA, no second KIE
    assert lab.store.get(NODE,node['id'],'alice')['status']=='response_received'
    assert not lab.store.get(NODE,node['id'],'alice').get('local_error')


async def test_recovery_reconciles_saved_gateway_response_and_unknown_never_resends(lab):
    pipeline,p,calls,_=setup(lab);row=pipeline.create('alice',p)
    # Simulate process death after Gateway commit, before attempt receives its response.
    original=lab.gateway.call
    async def crash(*args,**kw):
        await original(*args,**kw)
        raise asyncio.CancelledError()
    lab.gateway.call=crash;job=lab.store.claim()
    with pytest.raises(asyncio.CancelledError):await lab.worker.execute(job)
    with lab.store.tx() as db:db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(job['id'],))
    lab.gateway.call=original;recovered=lab.store.claim();assert recovered['id']==job['id'] and recovered['status']=='running'
    await lab.worker.execute(recovered);await drain(lab)
    assert len(calls)==4
    attempt=lab.store.get('benchmark.attempt',job['payload']['node_id']+':attempt','alice');assert attempt['recovered_gateway_response']


async def test_unknown_response_aborts_unsent_nodes_and_no_auto_retry(lab):
    pipeline,p,calls,_=setup(lab)
    async def unknown(*a,**kw):calls.append('sent');raise ModelFailure('timeout','unknown',True,True)
    lab.gateway._call=unknown;row=pipeline.create('alice',p);await drain(lab)
    detail=pipeline.detail('alice',row['id'])
    assert detail['pipeline']['status']=='aborted' and len(calls)==1
    assert sum(detail['report']['execution'].values())==4
    assert detail['report']['execution']['unknown']==1
    assert all(n['status'] not in ['ready','pending','running'] for n in detail['items'])
    assert detail['report']['cost']['unknown_requests']==1


async def test_stop_and_missing_usage_do_not_send_children(lab):
    pipeline,p,calls,_=setup(lab);row=pipeline.create('alice',p)
    pipeline.stop('alice',row['id'],dict(reason='停止全部后续请求',idempotency_key='stop'));await drain(lab)
    assert not calls and pipeline.report('alice',row['id'])['execution']['cancelled']==4
    row=pipeline.create('alice',dict(p,idempotency_key='missing'))
    original=lab.gateway._call
    async def missing(*a,**kw):
        result=await original(*a,**kw);result['usage']=None;result['cost_estimate']=None;return result
    lab.gateway._call=missing;await drain(lab)
    assert len(calls)==1 and pipeline.detail('alice',row['id'])['pipeline']['status']=='aborted'


async def test_explicit_kie_branch_rebuilds_descendants_not_global(lab):
    pipeline,p,calls,_=setup(lab,lambda m,n:'bad JSON');row=pipeline.create('alice',p);await drain(lab)
    parent=pipeline.detail('alice',row['id']);kie_node=next(n for n in parent['items'] if n['stage']=='kie')
    retry=pipeline.retry('alice',row['id'],dict(node_ids=[kie_node['id']],max_calls=3,reason='明确重试失败KIE和两个下游题',idempotency_key='retry'))
    assert retry['planned_units']==3 and retry['parent_pipeline_id']==row['id']
    async def repaired(owner,model,messages,purpose,request_id):
        calls.append(messages);raw=json.dumps(kie([message([10,10,110,90])])) if len(calls)==3 else '{"answer":"is_evidence"}'
        return dict(raw=raw,usage=dict(prompt_tokens=1,completion_tokens=1),cost_estimate=0,cost_currency='CNY',demo=False,latency_ms=1)
    lab.gateway._call=repaired;await drain(lab)
    assert len(calls)==5 and pipeline.detail('alice',retry['id'])['pipeline']['status']=='completed'
    assert pipeline.detail('alice',row['id'])['items']==parent['items']
    assert all(n['variant']!='full_image' for n in pipeline.detail('alice',retry['id'])['items'])


async def test_rescore_fixed_target_dictionary_no_calls(lab):
    pipeline,p,calls,b=setup(lab);row=pipeline.create('alice',p);await drain(lab);before=len(calls)
    a=b.save_review('alice',p['dataset_id'],'vqa',dict(reviewed(),target='not_evidence'))
    ss=pipeline.rescore('alice',row['id'],dict(annotation_ids={'vqa':a['id']},reason='新人工参考',idempotency_key='rescore'))
    report=pipeline.report('alice',row['id'],ss['id']);group=next(g for g in report['groups'] if g['variant']=='reference_guided_prediction' and g['field']=='evidence')
    assert group['correct']==0 and len(calls)==before
    matrix=report['classification']['reference_guided_prediction / evidence']
    assert matrix['labels']==['is_evidence','not_evidence'] and matrix['confusion'][json.dumps(['not_evidence','is_evidence'])]==1
    ss2=pipeline.rescore('alice',row['id'],dict(annotation_ids={},reason='保留上次新参考再评',idempotency_key='rescore2'))
    assert pipeline.report('alice',row['id'],ss2['id'])['classification']==report['classification']
    assert len(lab.store.list('benchmark.scoreset','alice'))==3


def test_association_granularity_and_invalid_reference_not_zero():
    m=scoring.kie(kie([message([0,0,200,160])]),200,160)['conversation']
    result=associate([10,10,20,20],m,200,160)
    assert result['status']=='below_threshold' and result['diagnostic']['reference_coverage']==1 and not result['diagnostic']['parent_certified']
    assert scoring.score(dict(task_family='vqa.amount',answer_kind='amount'),'bad JSON',{'answer_status':'unknown'},200,160)['score'] is None
    assert scoring.score(dict(task_family='vqa.identity',answer_kind='identity'),'bad JSON','avator_0',200,160)['score'] is None
    report=scoring.classification_report([('a','a')],['a','b']);assert report['labels']==['a','b'] and report['macro_f1']==.5


def test_pipeline_http_contract_owner_and_generic_retry_guard(accounts):
    _,_,alice,bob=accounts;store=alice.app.state.research['store'];d,_=seed(store)
    prompts=[]
    for family in ['kie','vqa']:
        r=alice.post('/v1/evaluation/task-prompts',json=dict(name='pipe'+family,family=family,parent_id=None,markdown='# task',note='first',idempotency_key=family));assert r.status_code==201;prompts.append(r.json()['id'])
    p=dict(dataset_id=d['id'],name='http fixture',task_ids=['vqa'],model_id='demo',kie_prompt_id=prompts[0],vqa_prompt_id=prompts[1],max_calls=2,idempotency_key='pipe')
    preview=alice.post('/v1/evaluation/benchmark-pipelines/preview',json=p);assert preview.status_code==200,preview.text
    assert preview.json()['maximum_calls']==2
    created=alice.post('/v1/evaluation/benchmark-pipelines',json=p);assert created.status_code==201,created.text
    id=created.json()['id'];assert bob.get('/v1/evaluation/benchmark-pipelines/'+id).status_code==404
    assert any(x['id']==id for x in alice.get('/v1/evaluation/history?category=benchmark').json()['items'])
    result=alice.get('/v1/evaluation/benchmark-pipelines/'+id);assert result.status_code==200
    job=next(j for j in store.jobs('alice') if j['kind']=='benchmark_pipeline')
    assert alice.post('/v1/research/jobs/'+job['id']+'/retry',json={'idempotency_key':'bad','task_ids':[]}).status_code==409


def test_concurrent_create_is_one_plan_and_one_model_snapshot(lab):
    from concurrent.futures import ThreadPoolExecutor
    pipeline,p,_,_=setup(lab);frozen=[];original=lab.gateway.freeze
    def freeze(*a,**kw):frozen.append(1);return original(*a,**kw)
    lab.gateway.freeze=freeze
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:pipeline.create('alice',p),range(4)))
    assert len({r['id'] for r in results})==1 and len(frozen)==1
    assert len(pipeline.rows('alice',results[0]['id']))==4
    assert len(lab.store.jobs('alice'))==2


async def test_budget_reservation_is_atomic_between_two_workers(lab):
    pipeline,p,calls,_=setup(lab);row=pipeline.create('alice',p)
    with lab.store.tx() as db:
        current=lab.store.get(KIND,row['id'],'alice',db);current['reserved_calls']=3;lab.store.put(KIND,current,'alice',db)
    original=lab.gateway._call
    async def pause(*a,**kw):await asyncio.sleep(.05);return await original(*a,**kw)
    lab.gateway._call=pause
    first,second=lab.store.claim(),lab.store.claim()
    await asyncio.gather(lab.worker.execute(first),lab.worker.execute(second));await drain(lab)
    assert len(calls)==1 and lab.store.get(KIND,row['id'],'alice')['reserved_calls']==4
    assert pipeline.report('alice',row['id'])['conserved']


async def test_same_bytes_distinct_logical_images_do_not_share_dependencies(lab):
    pipeline,p,calls,b=setup(lab);d=copy.deepcopy(b.dataset('alice',p['dataset_id']));tasks=copy.deepcopy(b.load(d['tasks']))
    duplicate=copy.deepcopy(tasks)
    for t in duplicate:t['task_id']+='2';t['image_name']='same-bytes-other-source.png'
    tasks+=duplicate;d['id']+='-two-images'
    for t in tasks:t['dataset_id']=d['id']
    d['images']['same-bytes-other-source.png']=d['images']['fixture.png'];d['tasks']=blob(lab.store,json.dumps(tasks).encode())
    with lab.store.tx() as db:lab.store.put('benchmark.dataset',d,'alice',db,immutable=True)
    async def response(owner,model,messages,purpose,request_id):
        calls.append(messages);user=messages[1]['content'];t=json.loads(user[0]['text'] if isinstance(user,list) else user)
        return dict(raw=json.dumps(kie([message([10,10,110,90])])) if t['task_type']=='kie.extract' else '{"answer":"is_evidence"}',usage=dict(prompt_tokens=1,completion_tokens=1),cost_estimate=0,cost_currency='CNY',latency_ms=1,demo=False)
    lab.gateway._call=response
    row=pipeline.create('alice',dict(p,dataset_id=d['id'],task_ids=['vqa','vqa2']));await drain(lab)
    result=pipeline.detail('alice',row['id']);assert len(calls)==4 and result['pipeline']['images']==2
    for n in result['items']:
        if n['stage']=='vqa':
            detail=pipeline.node_detail('alice',row['id'],n['id'])
            assert detail['match']['image_key']==detail['prediction']['image_key']==n['image_key']


def test_scoring_reference_perturbation_does_not_change_full_image_input(lab):
    pipeline,p,calls,b=setup(lab);dataset=p['dataset_id'];review=dict(reviewed(),question='Is this a conversation?',question_eligibility='reviewed_independent')
    a=b.save_review('alice',dataset,'global',review);r1=b.publish('alice',dict(dataset_id=dataset,task_ids=['global'],name='first',idempotency_key='r1'))
    run1=pipeline.create('alice',dict(p,task_ids=['global'],release_id=r1['id'],mode='official_reviewed'))
    b.save_review('alice',dataset,'global',dict(review,expected_version=1,target='not_evidence',bbox_xyxy=[120,100,190,150],idempotency_key='review2'))
    r2=b.publish('alice',dict(dataset_id=dataset,task_ids=['global'],name='second',idempotency_key='r2'))
    run2=pipeline.create('alice',dict(p,task_ids=['global'],release_id=r2['id'],mode='official_reviewed',idempotency_key='second'))
    n1=pipeline.rows('alice',run1['id'])[0];n2=pipeline.rows('alice',run2['id'])[0]
    assert n1['input_hash']==n2['input_hash'] and not calls
    assert pipeline.node_detail('alice',run1['id'],n1['id'])['input']==pipeline.node_detail('alice',run2['id'],n2['id'])['input']


async def test_pipeline_human_open_rubric_creates_audited_score_set(lab):
    pipeline,p,calls,b=setup(lab);row=pipeline.create('alice',p);await drain(lab);before=len(calls)
    n=next(n for n in pipeline.rows('alice',row['id']) if n['task_id']=='open')
    payload=dict(attempt_id=n['attempt_id'],dimensions=dict(faithfulness=4,relevance=3,support=3,no_unsupported_claims=4,uncertainty=4),process='人工核对证据和不确定性',findings='无需补造法律结论',suggestions='继续人工复核',prompt_id=None,idempotency_key='human')
    q=b.quality('alice',payload);assert b.quality('alice',payload)==q
    report=pipeline.report('alice',row['id']);g=next(g for g in report['groups'] if g['answer_kind']=='open_text')
    assert g['mean_scored']==.9 and g['pending_judgement']==0 and len(calls)==before
    assert len(lab.store.list('benchmark.scoreset','alice'))==2 and q['response_hash']


@pytest.mark.parametrize('window',['before_gateway_commit','after_gateway_commit'])
async def test_actual_worker_process_crash_uses_http_counter_and_never_reissues(lab,tmp_path,window):
    import subprocess,sys,threading
    from pathlib import Path
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            body=json.dumps(dict(raw=json.dumps(kie([message([10,10,110,90])])),usage=dict(prompt_tokens=1,completion_tokens=1),cost_estimate=0,cost_currency='CNY',demo=False,latency_ms=1)).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    child=None
    try:
        pipeline,p,_,_=setup(lab);original=lab.gateway.freeze
        lab.gateway.freeze=lambda *a,**kw:dict(original(*a,**kw),endpoint='http://127.0.0.1:'+str(server.server_port))
        row=pipeline.create('alice',dict(p,task_ids=['kie'],max_calls=1));marker=tmp_path/'crash-marker.txt'
        child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('pipeline_crash_worker.py')),str(lab.store.root.parent),str(marker),window],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(150):
            if marker.exists():break
            if child.poll() is not None:raise AssertionError(child.communicate()[1].decode())
            await asyncio.sleep(.05)
        assert marker.exists(),'worker did not reach crash window'
        child.kill();await asyncio.to_thread(child.communicate,timeout=10)
        with lab.store.tx() as db:db.execute("UPDATE jobs SET lease_until=0 WHERE kind='benchmark_pipeline'")
        reclaimed=lab.store.claim();assert reclaimed is not None
        await lab.worker.execute(reclaimed);await drain(lab)
        assert len(received)==1
        result=pipeline.detail('alice',row['id']);expected='response_received' if window=='after_gateway_commit' else 'unknown'
        assert result['items'][0]['status']==expected
        assert result['report']['conserved']
    finally:
        if child and child.poll() is None:child.kill();await asyncio.to_thread(child.communicate,timeout=10)
        await asyncio.to_thread(server.shutdown);server.server_close()


def test_report_100_questions_70_responses_63_correct_and_pending_interval(lab):
    pipeline,p,_,b=setup(lab);d=copy.deepcopy(b.dataset('alice',p['dataset_id']));original=copy.deepcopy(b.load(d['tasks']));kie_task=next(t for t in original if t['task_id']=='kie')
    base=next(t for t in original if t['task_id']=='vqa');tasks=[copy.deepcopy(base) for _ in range(100)]
    for i,t in enumerate(tasks):t['task_id']='example-'+str(i)
    d['id']+='-100';tasks.append(kie_task)
    for t in tasks:t['dataset_id']=d['id']
    d['tasks']=blob(lab.store,json.dumps(tasks).encode())
    with lab.store.tx() as db:lab.store.put('benchmark.dataset',d,'alice',db,immutable=True)
    row=pipeline.create('alice',dict(p,dataset_id=d['id'],task_ids=[t['task_id'] for t in tasks if t['task_id']!='kie'],max_calls=101))
    record=lab.store.get(KIND,row['id'],'alice');nodes=pipeline.rows('alice',row['id'])
    with lab.store.tx() as db:
        for n in nodes:
            if n['stage']=='kie':n['status']='response_received'
            else:
                i=int(n['task_id'].split('-')[1]);n['status']='response_received' if i<70 else 'blocked_no_match' if i<95 else 'service_failed'
                if i<70:
                    answer='is_evidence' if i<63 else 'not_evidence'
                    a=dict(id=n['id']+':attempt',pipeline_id=row['id'],status='completed',response=dict(raw=json.dumps(dict(answer=answer)),demo=False,cost_estimate=0,cost_currency='CNY',usage=dict(prompt_tokens=1,completion_tokens=1)))
                    n['attempt_id']=a['id'];lab.store.put('benchmark.attempt',a,'alice',db);pipeline._score('alice',record,n,a,db)
            lab.store.put(NODE,n,'alice',db)
    g=next(g for g in pipeline.report('alice',row['id'])['groups'] if g['answer_kind']=='categorical')
    assert (g['planned'],g['reference_valid'],g['responded'],g['scored_ref'])==(100,100,70,70)
    assert g['response_coverage']==.7 and g['conditional_accuracy']==.9 and g['binary_correct_delivery']==.63
    # One previously incorrect answer has not been judged: do not invent a zero or a final rank.
    with lab.store.tx() as db:
        n=next(n for n in nodes if n['task_id']=='example-69');sid=row['score_set_id'];old=lab.store.get('benchmark.score',n['id']+':'+sid,'alice',db)
        updated=dict(old,id='pending-score',result=dict(status='scoring_pending',score=None))
        lab.store.put('benchmark.score',updated,'alice',db,immutable=True)
        ss=lab.store.get('benchmark.scoreset',sid,'alice',db);ss.update(id='pending-set',overrides={x['id']:x['id']+':'+sid for x in nodes});ss['overrides'][n['id']]='pending-score'
        lab.store.put('benchmark.scoreset',ss,'alice',db,immutable=True)
    g=next(g for g in pipeline.report('alice',row['id'],'pending-set')['groups'] if g['answer_kind']=='categorical')
    assert g['pending_judgement']==1 and g['conditional_accuracy'] is None and g['binary_correct_delivery'] is None
    assert g['binary_delivery_bounds']==[.63,.64]


async def test_invalid_reference_geometry_is_not_counted_as_model_wrong(lab):
    pipeline,p,calls,b=setup(lab);d=copy.deepcopy(b.dataset('alice',p['dataset_id']));tasks=copy.deepcopy(b.load(d['tasks']));d['id']+='-invalid-geometry'
    for t in tasks:
        t['dataset_id']=d['id']
        if t['task_id']=='vqa':t['bbox_xyxy']=[-1,0,20,20]
    d['tasks']=blob(lab.store,json.dumps(tasks).encode())
    with lab.store.tx() as db:lab.store.put('benchmark.dataset',d,'alice',db,immutable=True)
    row=pipeline.create('alice',dict(p,dataset_id=d['id'],task_ids=['vqa']));await drain(lab)
    result=pipeline.detail('alice',row['id']);g=next(g for g in result['report']['groups'] if g['answer_kind']=='categorical')
    assert len(calls)==1 and g['planned']==1 and g['reference_valid']==0 and g['binary_correct_delivery'] is None
    assert next(n for n in result['items'] if n['stage']=='vqa')['status']=='invalid_input'


async def test_vqa_retry_preserves_original_prediction_and_input(lab):
    pipeline,p,calls,_=setup(lab)
    original=lab.gateway._call
    async def fail_one(owner,model,messages,purpose,id):
        user=messages[1]['content'];task=json.loads(user[0]['text'] if isinstance(user,list) else user)
        if task['track']=='vqa_matched_message' and 'evidence' in task['question']:
            calls.append(messages);raise ModelFailure('rate_limit','429 fixture',True)
        return await original(owner,model,messages,purpose,id)
    lab.gateway._call=fail_one;row=pipeline.create('alice',p);await drain(lab)
    failed=next(n for n in pipeline.rows('alice',row['id']) if n['task_id']=='vqa');before=len(calls)
    lab.gateway._call=original
    retry=pipeline.retry('alice',row['id'],dict(node_ids=[failed['id']],max_calls=1,reason='只重试字段问答',idempotency_key='vqa-retry'))
    await drain(lab);next_node=pipeline.rows('alice',retry['id'])[0]
    assert len(calls)==before+1 and next_node['input_hash']==failed['input_hash'] and next_node['prediction_id']==failed['prediction_id']
    assert pipeline.node_detail('alice',retry['id'],next_node['id'])['prediction']['id']==failed['prediction_id']


async def test_frozen_concurrency_one_applies_across_workers(lab):
    pipeline,p,calls,_=setup(lab);row=pipeline.create('alice',p);original=lab.gateway._call;active=0;peak=0
    async def slow(*a,**kw):
        nonlocal active,peak
        active+=1;peak=max(peak,active)
        try:await asyncio.sleep(.05);return await original(*a,**kw)
        finally:active-=1
    lab.gateway._call=slow
    first,second=lab.store.claim(),lab.store.claim()
    await asyncio.gather(lab.worker.execute(first),lab.worker.execute(second))
    for _ in range(50):
        job=lab.store.claim()
        if job:await lab.worker.execute(job)
        elif lab.store.get(KIND,row['id'],'alice')['status'] in ['completed','completed_with_issues']:break
        else:await asyncio.sleep(.05)
    assert peak==1 and len(calls)==4 and pipeline.report('alice',row['id'])['conserved']


async def test_late_gateway_response_can_be_reconciled_without_restarting_paid_children(lab):
    pipeline,p,calls,_=setup(lab);original_call=lab.gateway._call
    async def unknown(*a,**kw):calls.append('sent');raise ModelFailure('timeout','unknown',True,True)
    lab.gateway._call=unknown;row=pipeline.create('alice',p);await drain(lab)
    node=next(n for n in pipeline.rows('alice',row['id']) if n['status']=='unknown')
    attempt=lab.store.get('benchmark.attempt',node['attempt_id'],'alice');request=lab.store.get('evaluation.request',attempt['request_id'],'alice')
    command=dict(node_ids=[node['id']],reason='核对已落盘的迟到响应，不再次付费',idempotency_key='late')
    with pytest.raises(ValueError):pipeline.reconcile('alice',row['id'],command)
    with lab.store.tx() as db:
        request.update(status='completed',finished_at=now(),response=dict(raw=json.dumps(kie([message([10,10,110,90])])),usage=dict(prompt_tokens=1,completion_tokens=1),cost_estimate=0,cost_currency='CNY',demo=False,latency_ms=1))
        lab.store.put('evaluation.request',request,'alice',db)
    pipeline.reconcile('alice',row['id'],command);await drain(lab)
    result=pipeline.detail('alice',row['id'])
    assert result['pipeline']['status']=='aborted' and len(calls)==1
    assert sum(n['status']=='response_received' for n in result['items'])==1
    assert all(n['status']=='cancelled' for n in result['items'] if n['id']!=node['id'])
    assert result['report']['cost']['unknown_requests']==0
    child=next(n for n in pipeline.rows('alice',row['id']) if n['task_id']=='vqa')
    assert child['input_id']
    lab.gateway._call=original_call
    retry=pipeline.retry('alice',row['id'],dict(node_ids=[child['id']],max_calls=1,reason='只执行已冻结问答，不重复KIE',idempotency_key='late-vqa'))
    await drain(lab);assert len(calls)==2 and pipeline.rows('alice',retry['id'])[0]['stage']=='vqa'


async def test_local_recovery_preserves_received_execution_state_while_queued(lab,monkeypatch):
    pipeline,p,calls,_=setup(lab);original=pipeline._score
    def bad(*a,**kw):raise RuntimeError('local')
    monkeypatch.setattr(pipeline,'_score',bad);row=pipeline.create('alice',dict(p,task_ids=['kie']));await drain(lab)
    monkeypatch.setattr(pipeline,'_score',original);node=pipeline.rows('alice',row['id'])[0]
    pipeline.resume_local('alice',row['id'],dict(node_ids=[node['id']],reason='仅恢复本地，不撤销已返回计数',idempotency_key='resume-execution'))
    assert pipeline.rows('alice',row['id'])[0]['status']=='response_received'
    await drain(lab);assert len(calls)==1 and not pipeline.rows('alice',row['id'])[0].get('local_error')


@pytest.mark.parametrize('raw',['{"answer":NaN}','{"answer":Infinity}','{"answer":1e999}'])
async def test_nonfinite_model_json_retains_raw_but_never_breaks_result_serialization(lab,raw):
    pipeline,p,calls,_=setup(lab)
    async def output(*a,**kw):calls.append(1);return dict(raw=raw,usage=dict(prompt_tokens=1,completion_tokens=1),cost_estimate=0,cost_currency='CNY',demo=False,latency_ms=1)
    lab.gateway._call=output;row=pipeline.create('alice',dict(p,task_ids=['global']));await drain(lab)
    n=pipeline.rows('alice',row['id'])[0];data=pipeline.node_detail('alice',row['id'],n['id'])
    assert data['attempt']['response']['raw']==raw and n['schema_status']=='invalid'
    assert json.dumps(data,allow_nan=False) and pipeline.detail('alice',row['id'])['items'][0]['score']['result']['score']==0


async def test_export_deduplicates_parent_predictions_and_polling_omits_raw(lab):
    pipeline,p,calls,_=setup(lab);row=pipeline.create('alice',p);await drain(lab)
    data=pipeline.export('alice',row['id']);assert len(data['predictions'])==1 and len(data['matches'])==1 and len(data['inputs'])==4
    result=pipeline.detail('alice',row['id']);text=json.dumps(result)
    assert 'Synthetic fixture' not in text and '"response"' not in text and '"parsed"' not in text and '"prediction"' not in text


async def test_rescore_rejects_changed_question_or_guiding_region(lab):
    pipeline,p,_,b=setup(lab);row=pipeline.create('alice',p);await drain(lab)
    for i,change in enumerate([dict(question='A different question'),dict(bbox_xyxy=[20,20,100,80])]):
        payload=reviewed();payload.update(change);payload.update(expected_version=i,idempotency_key='changed-'+str(i))
        a=b.save_review('alice',p['dataset_id'],'vqa',payload)
        with pytest.raises(ValueError):pipeline.rescore('alice',row['id'],dict(annotation_ids={'vqa':a['id']},reason='不得换题或换输入',idempotency_key='bad-score-'+str(i)))


async def test_known_service_error_with_unknown_billing_stops_further_paid_work(lab):
    pipeline,p,calls,_=setup(lab)
    async def error(*a,**kw):calls.append('attempt');raise ModelFailure('rate_limit','HTTP 429 fixture',True)
    lab.gateway._call=error;row=pipeline.create('alice',p);await drain(lab);result=pipeline.detail('alice',row['id'])
    assert len(calls)==1 and result['pipeline']['status']=='aborted'
    assert result['report']['execution']['service_failed']==1 and result['report']['cost']['unknown_requests']==1
    assert result['report']['conserved'] and not any(n['status'] in ['ready','pending','running'] for n in result['items'])


async def test_multiple_local_recoveries_keep_parent_running_and_block_rescore(lab,monkeypatch):
    pipeline,p,calls,_=setup(lab);original=pipeline._score
    def bad(*a,**kw):raise RuntimeError('local scorer failure')
    monkeypatch.setattr(pipeline,'_score',bad);row=pipeline.create('alice',dict(p,task_ids=['kie','global']));await drain(lab)
    monkeypatch.setattr(pipeline,'_score',original)
    command=dict(node_ids=[],reason='恢复全部本地阶段',idempotency_key='recover-all')
    pipeline.resume_local('alice',row['id'],command)
    job=lab.store.claim();await lab.worker.execute(job);current=lab.store.get(KIND,row['id'],'alice')
    assert current['status']=='running' and current['pending_local_jobs']==1
    with pytest.raises(Conflict):pipeline.rescore('alice',row['id'],dict(annotation_ids={},reason='仍在恢复不能固定评分',idempotency_key='too-early'))
    with pytest.raises(ValueError):pipeline.resume_local('alice',row['id'],dict(command,idempotency_key='duplicate-local'))
    await drain(lab);current=lab.store.get(KIND,row['id'],'alice')
    assert current['status']=='completed' and current['pending_local_jobs']==0 and len(calls)==2
    assert all(n['local_processing']=='completed' for n in pipeline.rows('alice',row['id']))


async def test_sample_scope_includes_all_image_questions_and_keeps_stage_records(lab):
    pipeline,p,calls,b=setup(lab)
    p.update(task_ids=[],image_names=['fixture.png'])
    samples=b.sample_rows('alice',p['dataset_id'])
    assert samples['total']==1
    assert samples['items'][0]['maximum_calls']==4
    assert samples['items'][0]['kie']==1 and samples['items'][0]['regions']==1
    assert samples['items'][0]['regional_vqa']==2 and samples['items'][0]['global_vqa']==1
    preview=pipeline.preview('alice',p)
    assert preview['selected_tasks']==4 and preview['selection_unit']=='sample' and not calls
    row=pipeline.create('alice',p);await drain(lab)
    assert row['selection_unit']=='sample' and row['selected_image_names']==['fixture.png']
    result=pipeline.sample_results('alice',row['id'])
    assert result['total']==1 and result['items'][0]['planned_units']==4
    assert result['items'][0]['kie']=={'response_received':1}
    assert result['items'][0]['vqa']=={'response_received':3}
    assert result['items'][0]['association']=={'matched':1}
    assert len(calls)==4 and len(lab.store.list(NODE,'alice'))==4
    with pytest.raises(KeyError):pipeline.sample_results('bob',row['id'])


def test_sample_scope_rejects_ambiguous_foreign_and_underfunded_plans(lab):
    pipeline,p,calls,_=setup(lab)
    for patch in [dict(image_names=['fixture.png']),dict(task_ids=[],image_names=['missing.png']),dict(task_ids=[],image_names=['fixture.png','fixture.png']),dict(task_ids=[],image_names=['fixture.png'],all_tasks=True),dict(task_ids=[],image_names=['fixture.png'],max_calls=3)]:
        with pytest.raises(ValueError):pipeline.create('alice',dict(p,**patch))
    assert not calls and not lab.store.list(KIND,'alice')


def test_sample_listing_and_scope_preserve_same_bytes_as_distinct_logical_images(lab):
    pipeline,p,calls,b=setup(lab);d=b.dataset('alice',p['dataset_id']);tasks=copy.deepcopy(b.load(d['tasks']))
    all_tasks=[]
    for index,name in enumerate(['fixture.png','同字节第二图.png','third.png']):
        for original in tasks:
            t=copy.deepcopy(original);t.update(task_id=original['task_id']+str(index),image_name=name)
            if t.get('region_id'):t['region_id']+=':'+str(index)
            all_tasks.append(t)
    all_tasks.append(dict(migration_record_type='review_note',image_name='comment-only.png'))
    with lab.store.tx() as db:
        d.update(tasks=blob(lab.store,json.dumps(all_tasks).encode()));lab.store.put('benchmark.dataset',d,'alice',db)
    listed=b.sample_rows('alice',d['id'],limit=1)
    assert listed['total']==3 and len(listed['items'])==1 and listed['next_offset']==1
    assert b.sample_rows('alice',d['id'],q='同字节')['total']==1
    assert b.sample_rows('alice',d['id'],offset=3)['items']==[]
    with pytest.raises(KeyError):b.sample_rows('bob',d['id'])
    p.update(task_ids=[],image_names=['fixture.png','同字节第二图.png','third.png'],max_calls=12)
    row=pipeline.create('alice',p)
    assert row['images']==3 and row['planned_units']==12 and not calls
    result=pipeline.sample_results('alice',row['id'],limit=2)
    assert result['total']==3 and result['next_offset']==2
    assert all(i['planned_units']==4 and i['status']=='running' for i in result['items'])
    assert pipeline.sample_results('alice',row['id'],offset=2)['next_offset'] is None


async def test_sample_summary_retains_blocked_questions_and_no_match_region(lab):
    pipeline,p,calls,_=setup(lab,lambda m,n:json.dumps(kie([])))
    p.update(task_ids=[],image_names=['fixture.png'])
    row=pipeline.create('alice',p);await drain(lab)
    result=pipeline.sample_results('alice',row['id'])['items'][0]
    assert result['planned_units']==4 and result['responded']==2
    assert result['vqa']=={'blocked_no_match':2,'response_received':1}
    assert result['association']=={'no_message':1} and result['status']=='completed_with_issues'


def test_sample_http_routes_owner_and_scope_validation(accounts):
    _,_,alice,bob=accounts;store=alice.app.state.research['store'];d,_=seed(store)
    assert alice.get('/v1/evaluation/benchmarks/'+d['id']+'/samples').json()['items'][0]['maximum_calls']==3
    assert bob.get('/v1/evaluation/benchmarks/'+d['id']+'/samples').status_code==404
    assert alice.get('/v1/evaluation/benchmarks/'+d['id']+'/samples?limit=101').status_code==422
    payload=dict(dataset_id=d['id'],name='sample http',image_names=['fixture.png'],model_id='demo',max_calls=3,idempotency_key='sample-http')
    prompts=alice.post('/v1/evaluation/benchmark-pipelines/default-prompts').json()
    payload.update(kie_prompt_id=next(p['id'] for p in prompts if p['family']=='kie'),vqa_prompt_id=next(p['id'] for p in prompts if p['family']=='vqa'))
    preview=alice.post('/v1/evaluation/benchmark-pipelines/preview',json=payload)
    assert preview.status_code==200 and preview.json()['selected_tasks']==3
    created=alice.post('/v1/evaluation/benchmark-pipelines',json=payload);assert created.status_code==201
    pid=created.json()['id']
    assert alice.get('/v1/evaluation/benchmark-pipelines/'+pid+'/samples').json()['total']==1
    assert bob.get('/v1/evaluation/benchmark-pipelines/'+pid+'/samples').status_code==404
    assert alice.post('/v1/evaluation/benchmark-pipelines',json=payload).json()['id']==pid


async def test_legacy_sample_results_reconstruct_regions_from_frozen_tasks(lab):
    pipeline,p,calls,_=setup(lab);row=pipeline.create('alice',p);await drain(lab)
    with lab.store.tx() as db:
        for n in pipeline.rows('alice',row['id'],db):
            n.pop('association_key',None);lab.store.put(NODE,n,'alice',db)
    result=pipeline.sample_results('alice',row['id'])['items'][0]
    assert result['planned_regions']==1 and result['association']=={'matched':1}
    assert result['planned_units']==4 and len(calls)==4


def test_empty_sample_scope_preserves_legacy_create_idempotency(lab):
    pipeline,p,calls,_=setup(lab);row=pipeline.create('alice',p)
    assert pipeline.create('alice',dict(p,image_names=[]))['id']==row['id']
    assert len(lab.store.list(KIND,'alice'))==1 and not calls


async def test_full_sample_with_only_global_questions_still_plans_kie_without_inventing_iou(lab):
    pipeline,p,calls,b=setup(lab);d=b.dataset('alice',p['dataset_id'])
    tasks=[t for t in b.load(d['tasks']) if t['task_family']=='kie.extract' or t['task_id']=='global']
    with lab.store.tx() as db:
        d['tasks']=blob(lab.store,json.dumps(tasks).encode());lab.store.put('benchmark.dataset',d,'alice',db)
    p.update(task_ids=[],image_names=['fixture.png'],max_calls=2)
    row=pipeline.create('alice',p);await drain(lab)
    result=pipeline.sample_results('alice',row['id'])['items'][0]
    assert result['kie']=={'response_received':1} and result['vqa']=={'response_received':1}
    assert result['planned_regions']==0 and result['association']=={} and len(calls)==2
