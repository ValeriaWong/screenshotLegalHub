import asyncio,copy,json,math
import pytest
from screenshotlegal.research.benchmark import Benchmark,DEFAULTS
from screenshotlegal.research import benchmark_scoring as s,audit
from screenshotlegal.research.store import Conflict
from screenshotlegal.research.history import history
from screenshotlegal.research.operations import Operations
from test_research_products import lab,drain
from test_accounts_ingestion import accounts
from benchmark_fixtures import seed

def reviewed(**kwargs):
    return dict(expected_version=0,verdict='pass',target='is_evidence',question='Visible question evidence',bbox_xyxy=[10,10,110,90],region_type='other',image_identity_confirmed=True,case_group='case-one',split='development',reason='对照原图人工核对',suggestions='保持原图',idempotency_key='review',**kwargs)
def prompt(b,family='vqa'):
    return b.save_prompt('alice',dict(name='task',family=family,parent_id=None,markdown=DEFAULTS[family],note='initial',idempotency_key='prompt'+family))
def run_payload(p,**kw):
    return dict(dataset_id='benchmark.fixture',name='fixture run',task_ids=['vqa'],track='vqa_image_full',mode='development_reference',release_id=None,model_id='demo',prompt_id=p['id'],max_calls=1,iou_threshold=.6,upstream_attempt_id=None,idempotency_key='run',**kw)
def message(bbox=[1,1,20,20],**kw):
    return dict(timestamp=None,speaker='avator_0',content='Visible text',message_bbox=dict(zip(['min_x','min_y','max_x','max_y'],bbox)),image=None,transfer=None,file=None,**kw)
def kie(messages=None): return dict(dialog_name=None,conversation=messages if messages is not None else [message()])

@pytest.mark.parametrize('bad',[[0,0,0,1],[1,0,0,1],[0,0,float('nan'),1],[0,0,float('inf'),1],[-1,0,1,2],[0,0,201,2],[False,0,1,2]])
def test_bbox_rejects_invalid(bad):
    with pytest.raises(ValueError):s.box(bad,200,160)
def test_geometry_rounding_and_legacy_math_are_separate():
    assert s.box([0,0,200+1e-10,160],200,160)==[0.,0.,200.,160.]
    from screenshotlegal.research.benchmark_legacy import iou_xyxy
    assert iou_xyxy([0,0,1,1],[0,0,1,1])==1/(1+1e-9)
    assert s.iou([0,0,1,1],[0,0,1,1])==1

def test_matching_max_cardinality_not_greedy_and_penalizes_extra():
    g=[dict(bbox=[0,0,10,10]),dict(bbox=[5,0,15,10])];p=[dict(bbox=[2,0,12,10]),dict(bbox=[0,0,7,10]),dict(bbox=[100,100,110,110])]
    r=s.match(g,p,.3)
    assert r['tp']==2 and r['fp']==1 and r['fn']==0
    assert {(m['gold'],m['prediction']) for m in r['matches']}=={(0,1),(1,0)}
    assert s.match(g,p,.3)==r
    assert s.match([dict(bbox=[0,0,10,10],region_type='avatar')],[dict(bbox=[0,0,10,10],region_type='message')])['tp']==0

def test_fields_unknown_amount_legal_identity_and_unicode():
    assert s.field('amount','未知',{'answer_status':'known','value':'0','currency':'CNY'})['score'] is None
    assert s.field('amount',{'answer_status':'known','value':'2.00','currency':'CNY'},{'answer_status':'known','value':'2','currency':'USD'})['score']==0
    assert s.field('amount',{'answer_status':'known','value':'2.00','currency':'CNY'},{'answer_status':'known','value':'2','currency':'CNY'})['score']==1
    assert s.field('identity','avator_0','avator_0')['score'] is None
    assert s.field('open_text','same','same')['score'] is None
    assert s.field('text','é','e\u0301')['normalized_exact']
    assert s.field('filename','File.PDF','file.pdf')['score']==0
    assert s.field('set',['a','b'],['b','a'])['score']==1
    assert s.classification_report([('a','a'),('b','a')])['macro_f1']==pytest.approx(1/3)

def test_kie_schema_keeps_every_field_and_counts_missed_extra():
    data=kie();r=s.score(dict(task_family='kie.extract'),json.dumps(data),None,200,160)
    assert r['structure_valid'] and r['score'] is None
    extra=copy.deepcopy(data);extra['conversation'].append(message([50,50,60,60]));r=s.score(dict(task_family='kie.extract'),json.dumps(extra),data,200,160)
    assert r['detection']['fp']==1 and r['score']==pytest.approx(2/3)
    assert {'image','transfer','file'}<=set(r['prediction']['conversation'][0])
    bad=kie([dict(content='only')]);assert s.score(dict(task_family='kie.extract'),json.dumps(bad),data,200,160)['status']=='format_failure'
    assert s.parse(chr(96)*3+'json\n{"answer":"yes"}\n'+chr(96)*3)=={'answer':'yes'}

def test_review_binding_cas_split_and_comments_visible_in_audit(lab):
    d,t=seed(lab.store);b=Benchmark(lab.store)
    with pytest.raises(KeyError):b.detail('bob',d['id'],'vqa')
    p=reviewed();a=b.save_review('alice',d['id'],'vqa',p)
    assert b.save_review('alice',d['id'],'vqa',p)==a
    with pytest.raises(Conflict):b.save_review('alice',d['id'],'vqa',dict(p,idempotency_key='stale'))
    with pytest.raises(Conflict):b.save_review('alice',d['id'],'open',dict(p,target='analysis',split='holdout',idempotency_key='leak'))
    c=b.comment('alice',d['id'],'vqa',dict(body='可只提意见，不改答案',use_for_generation=True,idempotency_key='comment'))
    detail=b.detail('alice',d['id'],'vqa');assert detail['comments'][0]['id']==c['id'] and len(detail['quality'])==2
    release=b.publish('alice',dict(dataset_id=d['id'],task_ids=['vqa'],name='published',idempotency_key='release'))
    updated=b.save_review('alice',d['id'],'vqa',dict(p,expected_version=1,target='not_evidence',idempotency_key='v2'))
    assert updated['version']==2 and release['entries'][0]['annotation']['target']=='is_evidence'
    events=audit.query(lab.store,'alice',q='benchmark.annotation',limit=50)['items'];assert events
    ops=Operations(lab.store);assert ops.resolve('alice',a['id'])['kind']=='benchmark.annotation'

def test_input_tracks_never_include_target_matched_text_or_notes(lab):
    d,t=seed(lab.store);b=Benchmark(lab.store)
    for track,id in [('kie_image','kie'),('vqa_image_full','open'),('vqa_image_region','open')]:
        frozen=b.freeze_task('alice',d['id'],id,track);text=json.dumps(frozen['input'])
        assert 'LEGACY_PRIVATE_ANSWER' not in text and 'target' not in text and 'legacy_raw' not in text
        assert ('roi_xyxy' in frozen['input'])==(track=='vqa_image_region')
    with pytest.raises(ValueError,match='禁止替换成人工文本'):b.freeze_task('alice',d['id'],'open','vqa_predicted_text')
    with pytest.raises(ValueError):b.freeze_task('alice',d['id'],'kie','vqa_image_region')

async def test_worker_model_response_scoring_and_offline_rescore(lab):
    d,_=seed(lab.store);b=Benchmark(lab.store,lab.gateway);lab.worker.benchmark=b;p=prompt(b)
    payload=run_payload(p);r=b.create_run('alice',payload)
    assert b.create_run('alice',payload)['id']==r['id']
    await drain(lab);result=b.results('alice',r['id'])
    assert result['report']['returned']==1 and result['scores'][0]['result']['score'] is None and result['scores'][0]['result']['status']=='unscored_demo'
    before=len(lab.store.list('evaluation.request','alice'))
    b.rescore('alice',r['id'],dict(annotation_id=None,reason='离线核对',idempotency_key='rescore'))
    assert len(lab.store.list('benchmark.score','alice'))==2 and len(lab.store.list('evaluation.request','alice'))==before
    assert any(x['id']==r['id'] for x in history(lab.store,'alice','benchmark')['items'])
    with pytest.raises(ValueError):b.create_run('alice',dict(payload,mode='official_reviewed',idempotency_key='no-release'))

async def test_formal_snapshot_and_raw_before_scoring(lab):
    d,_=seed(lab.store);b=Benchmark(lab.store,lab.gateway);lab.worker.benchmark=b;p=prompt(b)
    a=b.save_review('alice',d['id'],'vqa',reviewed());release=b.publish('alice',dict(dataset_id=d['id'],task_ids=['vqa'],name='R',idempotency_key='R'))
    calls=[]
    def freeze(*args,**kw):return dict(id='mock',config_id='mock',name='mock',parameters={})
    async def call(owner,model,messages,purpose,id):
        assert 'is_evidence' not in json.dumps(messages);calls.append(id);return dict(raw='{"answer":"is_evidence"}',usage=None,latency_ms=1,demo=False)
    lab.gateway.freeze=freeze;lab.gateway.call=call
    r=b.create_run('alice',dict(run_payload(p),mode='official_reviewed',release_id=release['id']))
    b.save_review('alice',d['id'],'vqa',dict(reviewed(),expected_version=1,target='not_evidence',idempotency_key='next'))
    await drain(lab);res=b.results('alice',r['id']);assert res['scores'][0]['result']['score']==1 and len(calls)==1
    b.rescore('alice',r['id'],dict(annotation_id=None,reason='再评旧回答',idempotency_key='again'));assert len(calls)==1

async def test_interrupted_request_becomes_unknown_and_is_not_automatically_reissued(lab):
    d,_=seed(lab.store);b=Benchmark(lab.store,lab.gateway);lab.worker.benchmark=b;p=prompt(b);r=b.create_run('alice',run_payload(p));job=lab.store.claim()
    with lab.store.tx() as db:
        job['phase']='calling_model';lab.store.save_job(db,job,job['lease_token'])
        lab.store.put('benchmark.attempt',dict(id='begun',run_id=r['id'],dataset_id=d['id'],task_id='vqa',task_family='vqa.categorical',image_sha256=d['images']['fixture.png']['sha256'],status='calling_model',created_at='now'),'alice',db)
        db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(job['id'],))
    unknown=lab.store.claim();assert unknown['status']=='unknown';await lab.worker.execute(unknown)
    assert b.results('alice',r['id'])['attempts'][0]['status']=='unknown' and lab.store.list('evaluation.request','alice')==[]

def test_http_owner_prompts_drafts_and_feedback(accounts):
    _,_,alice,bob=accounts;store=alice.app.state.research['store'];seed(store)
    base='/v1/review/benchmarks/benchmark.fixture/tasks/vqa'
    assert alice.get('/v1/evaluation/benchmarks').json()[0]['id']=='benchmark.fixture'
    assert bob.get(base).status_code==404
    draft=dict(expected_version=0,draft_id='first',base_version=0,content={'note':'keep this text'})
    assert alice.put(base+'/draft',json=draft).status_code==200
    assert alice.put(base+'/draft',json=draft).status_code==409
    assert bob.get(base+'/draft').status_code==404
    assert alice.put(base,json=reviewed()).status_code==200
    assert alice.post(base+'/comments',json=dict(body='feedback',use_for_generation=True,idempotency_key='c')).status_code==201
    assert len(alice.get('/v1/studio/benchmark-feedback?dataset_id=benchmark.fixture').json())==1
    assert bob.get('/v1/evaluation/history?category=benchmark').json()['items']==[]
    p=dict(name='extract',family='kie',markdown='# task',note='first',parent_id=None,idempotency_key='p')
    assert alice.post('/v1/evaluation/task-prompts',json=p).status_code==201
    assert alice.post('/v1/evaluation/task-prompts',json=dict(p,note='stale',idempotency_key='p2')).status_code==409
    assert '# task' in alice.get('/v1/evaluation/task-prompts/export?name=extract').text

async def test_open_analysis_quality_is_append_only_bound_to_raw_answer_and_audited(lab):
    d,_=seed(lab.store);b=Benchmark(lab.store,lab.gateway);lab.worker.benchmark=b;p=prompt(b)
    lab.gateway.freeze=lambda *a,**kw:dict(id='mock',config_id='mock',name='mock')
    async def call(*args):return dict(raw='{"answer":"输入不足，不能认定法律责任","evidence":[]}',demo=False,usage=None,latency_ms=1)
    lab.gateway.call=call
    r=b.create_run('alice',dict(run_payload(p),task_ids=['open']));await drain(lab)
    attempt=b.results('alice',r['id'])['attempts'][0]
    payload=dict(attempt_id=attempt['id'],dimensions=dict(faithfulness=4,relevance=3,support=3,no_unsupported_claims=4,uncertainty=4),process='对照可见内容逐项检查',findings='表达了不确定性',suggestions='补充原始证据',prompt_id=None,idempotency_key='rubric')
    q=b.quality('alice',payload);assert b.quality('alice',payload)==q
    assert q['response_hash'] and q['asset_sha256'] and q['input_hash']
    res=b.results('alice',r['id']);assert len(res['scores'])==2 and res['scores'][0]['result']['legal_correctness'] is None
    with pytest.raises(KeyError):b.quality('bob',payload)
    with pytest.raises(ValueError):b.quality('alice',dict(payload,dimensions={'faithfulness':5},idempotency_key='bad'))

def test_review_heads_do_not_overwrite_other_dataset_versions(lab):
    d,_=seed(lab.store);seed(lab.store,dataset_id='benchmark.new-snapshot');b=Benchmark(lab.store)
    a=b.save_review('alice',d['id'],'vqa',reviewed());b.save_review('alice','benchmark.new-snapshot','vqa',dict(reviewed(),idempotency_key='other'))
    assert b.detail('alice',d['id'],'vqa')['annotation']['id']==a['id']

async def test_legacy_prediction_reference_and_failed_upstream_are_frozen_without_gold_fallback(lab):
    d,_=seed(lab.store);b=Benchmark(lab.store,lab.gateway);lab.worker.benchmark=b;p=prompt(b)
    from screenshotlegal.research.benchmark_import import blob
    raw=blob(lab.store,json.dumps(dict(items=[dict(image_tail='fixture.png',response=json.dumps(kie())),dict(image_tail='fixture.png',error='old failure')])).encode())
    with lab.store.tx() as db:lab.store.put('benchmark.history',dict(id='legacy',dataset_id=d['id'],role='raw_attempts',raw=raw,summary={'rows':2},name='old',created_at='now',status='imported'),'alice',db)
    task=b.freeze_task('alice',d['id'],'open','vqa_predicted_text',upstream_id='legacy:0')
    assert 'images' not in task['input'] and 'LEGACY_PRIVATE_ANSWER' not in json.dumps(task['input'])
    assert task['input']['upstream_source']['json_pointer']=='/items/0'
    r=b.create_run('alice',dict(run_payload(p),task_ids=['open'],track='vqa_predicted_text',upstream_attempt_id='legacy:1'))
    await drain(lab);result=b.results('alice',r['id'])
    assert result['run']['status']=='failed' and result['report']['blocked_upstream']==1 and result['report']['attempted']==0
    assert lab.store.list('evaluation.request','alice')==[]

def test_abstention_is_not_a_format_error_and_unknown_reference_stays_unscored():
    assert s.field('categorical','is_evidence',None)['status']=='abstained'
    target={'answer_status':'known','value':'0','currency':'CNY'}
    assert s.field('amount',target,{'answer_status':'unknown','value':None,'currency':None})['status']=='abstained'
    assert s.field('amount',target,{'answer_status':'unknown'})['score']==0
    assert s.field('amount','未知',None)['score'] is None

async def test_explicit_retry_clones_frozen_input_and_preserves_unknown_attempt(lab):
    d,_=seed(lab.store);b=Benchmark(lab.store,lab.gateway);lab.worker.benchmark=b;p=prompt(b)
    from screenshotlegal.research.gateway import ModelFailure
    count=[]
    async def call(*args):
        count.append(1)
        if len(count)==1:raise ModelFailure('timeout','unknown',True,True)
        return dict(raw='{"answer":"is_evidence"}',demo=True,latency_ms=1,usage=None)
    lab.gateway.call=call;r=b.create_run('alice',run_payload(p));await drain(lab)
    before=b.results('alice',r['id']);assert before['attempts'][0]['status']=='unknown'
    retry=b.retry('alice',r['id'],dict(task_ids=[],idempotency_key='retry'))
    assert retry['tasks']==before['run']['tasks'] and retry['model']==before['run']['model'] and retry['parent_run_id']==r['id']
    assert b.retry('alice',r['id'],dict(task_ids=[],idempotency_key='retry'))['id']==retry['id']
    await drain(lab);assert len(count)==2 and b.results('alice',r['id'])==before and b.results('alice',retry['id'])['run']['status']=='completed'
