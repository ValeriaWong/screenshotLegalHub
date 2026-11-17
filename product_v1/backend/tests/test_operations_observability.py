import json
import pytest
import httpx
from pydantic import SecretStr, ValidationError
from screenshotlegal.domain.settings.models import ModelConfiguration
from screenshotlegal.research.gateway import Gateway
from screenshotlegal.research.operations import Operations
from screenshotlegal.research import audit
from screenshotlegal.research.contracts import *
from test_research_products import lab, create, prompt, drain, release
from test_accounts_ingestion import accounts, model

def configuration(**kw):
    return ModelConfiguration(name='reasoning',base_url='https://unit.test/v1',model_name='reasoning',api_key=SecretStr('test-only-key'),allow_external_egress=True,**kw)

async def test_optional_budget_and_per_model_prices_freeze(lab,workspace,monkeypatch):
    pref=workspace.preferences('alice');saved=pref.save_model(configuration());g=Gateway(lab.store,workspace);snap=g.freeze('alice',saved.id)
    assert 'max_tokens' not in snap['parameters'] and snap['billing']['input_token_price'] is None
    captured=[];client=httpx.AsyncClient
    def reply(req):
        captured.append(json.loads(req.content));return httpx.Response(200,json={'choices':[{'message':{'content':'OK'},'finish_reason':'stop'}],'usage':{'prompt_tokens':2,'completion_tokens':1}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(reply),**kw))
    await g.call('alice',snap,[],'probe','test')
    assert 'max_tokens' not in captured[0]
    pref.save_model(configuration(max_output_tokens=9000,input_token_price=2,output_token_price=4,price_currency='USD'),saved.id)
    updated=g.freeze('alice',saved.id)
    assert updated['parameters']['max_tokens']==9000 and updated['billing']=={'input_token_price':2,'output_token_price':4,'currency':'USD'}
    assert snap['billing']['input_token_price'] is None
    assert pref.models()[0].max_output_tokens==9000
    for changes in [dict(max_output_tokens=0),dict(input_token_price=-1),dict(output_token_price=float('inf'))]:
        with pytest.raises(ValidationError):configuration(**changes)

async def test_empty_length_failure_preserves_usage_without_replay(lab,workspace,monkeypatch):
    g=Gateway(lab.store,workspace);saved=workspace.preferences('alice').save_model(configuration(max_output_tokens=10));lab.worker.gateway=g
    source=create(lab);p=prompt(lab,'review');calls=[];client=httpx.AsyncClient
    def reply(req):
        calls.append(req);return httpx.Response(200,headers={'x-request-id':'provider-1'},json={'choices':[{'message':{'content':None},'finish_reason':'length'}],'usage':{'prompt_tokens':30,'completion_tokens':10,'completion_tokens_details':{'reasoning_tokens':10}}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(reply),**kw))
    job=lab.review.queue_quality('alice',source['sample']['id'],QualityRun(revision=1,prompt_id=p['id'],model_id=saved.id,idempotency_key='length'),g.freeze('alice',saved.id))
    await drain(lab);row=lab.store.job(job['id'],'alice')
    assert row['status']=='failed' and row['error']['category']=='output_limit'
    evidence=row['checkpoints']['failure:response'];assert evidence['finish_reason']=='length' and evidence['usage']['completion_tokens']==10
    assert evidence['provider_request_id']=='provider-1' and len(calls)==1
    assert 'test-only-key' not in dumps(row)

async def test_unassessed_dimension_does_not_invent_zero(lab,monkeypatch):
    source=create(lab);p=prompt(lab,'review')
    async def reply(*args):return dict(raw=dumps(dict(verdict='revise',score=80,dimensions={'text':80,'visual':None},findings='no image',process='text only')),usage=None,latency_ms=1,demo=False)
    monkeypatch.setattr(lab.gateway,'call',reply)
    lab.review.queue_quality('alice',source['sample']['id'],QualityRun(revision=1,prompt_id=p['id'],model_id='demo',idempotency_key='null'),lab.gateway.freeze('alice','demo'))
    await drain(lab);q=next(q for q in lab.review.active_quality('alice') if q['method']=='model')
    assert q['dimensions']=={'text':80} and 'null' in q['response']['raw']

async def test_each_model_uses_its_frozen_billing_and_zero_is_free(lab,workspace,monkeypatch):
    _,r=await release(lab);pref=workspace.preferences('alice');a=pref.save_model(configuration(input_token_price=2,output_token_price=3));b=pref.save_model(configuration(input_token_price=0,output_token_price=0));c=pref.save_model(configuration());d=pref.save_model(configuration(input_token_price=2,output_token_price=3))
    g=Gateway(lab.store,workspace);lab.evaluation.gateway=g;lab.worker.gateway=g
    run=lab.evaluation.create_run('alice',EvaluationCreate(name='prices',release_id=r['id'],model_ids=[a.id,b.id,c.id,d.id],idempotency_key='prices'))
    pref.save_model(configuration(input_token_price=999,output_token_price=999),a.id)
    async def reply(*args):return dict(raw='answer',usage={'prompt_tokens':100} if args[1]['config_id']==d.id else {'prompt_tokens':100,'completion_tokens':10},latency_ms=1,demo=False)
    monkeypatch.setattr(g,'call',reply);await drain(lab);result=lab.evaluation.results('alice',run['id'])
    costs={m['model']['config_id']:m['cost'] for m in result['report']['models']}
    assert costs[a.id]==pytest.approx(2*(100*2+10*3)/1000000) and costs[b.id]==0 and costs[c.id] is None and costs[d.id] is None


def test_keyword_dates_aggregation_cursor_and_owner_scope(lab):
    with lab.store.tx() as db:
        for owner,when,reason in [('alice','2026-10-23T16:30:00+00:00','DeepSeek output_limit'),('alice','2026-10-24T16:30:00+00:00','DeepSeek response_parse'),('bob','2026-10-23T17:00:00+00:00','DeepSeek private')]:
            token=audit.context.set({'correlation_id':'flow-A','actor_id':'agent','actor_type':'agent'})
            audit.emit(db,owner,'probe.failed','evaluation.probe',uid('probe'),reason=reason,occurred_at=when,details={'max_tokens':8192,'api_key':'secret-value'})
            audit.context.reset(token)
    f=dict(q='DeepSeek output_limit',since='2026-10-24T00:00:00+08:00',until='2026-10-24T23:59:59+08:00',correlation_id='flow-A')
    rows=audit.query(lab.store,'alice',**f)['items'];assert len(rows)==1
    assert rows[0]['context']['max_tokens']==8192 and rows[0]['context']['api_key']=='[redacted]'
    assert 'INFO | review' in rows[0]['formatted_log']
    total=audit.summary(lab.store,'alice',group_by='day',**f);assert total['groups']=={'2026-10-24':1}
    assert not audit.query(lab.store,'alice',q="%' OR 1=1 --")['items']
    first=audit.query(lab.store,'alice',limit=1);second=audit.query(lab.store,'alice',limit=1,cursor=first['next_cursor'])
    assert first['items'][0]['id']!=second['items'][0]['id']


def test_operations_show_unscored_probes_and_resolve_real_objects(lab):
    source=create(lab);ops=Operations(lab.store);sid=source['sample']['id']
    with lab.store.tx() as db:lab.store.put('evaluation.probe',dict(id='probe-test',scope='development_qa',flow_id='flow-test',sample_id=sid,mode='image',success=True,score=None,response={'raw':'actual answer'},created_at=now()),'alice',db,immutable=True)
    assert ops.rows('alice',kind='evaluation.probe')['total']==1
    assert ops.rows('bob',kind='evaluation.probe')['total']==0
    assert ops.get('alice','evaluation.probe','probe-test')['body']['score'] is None
    assert ops.resolve('alice',sid)['href']=='/review.html?sample='+sid
    assert ops.resolve('alice',source['job_id'])['kind']=='job'
    with pytest.raises(KeyError):ops.get('bob','evaluation.probe','probe-test')
    with pytest.raises(KeyError):ops.resolve('bob',sid)


def test_operation_http_auth_search_export_and_scope(accounts):
    w,admin,alice,bob=accounts
    sample=alice.post('/v1/review/samples',json=dict(dataset='ops',content={'title':'Needle 原始测试','messages':[{'id':'m1','text':'test'}]},note='keyword-needle',idempotency_key='sample')).json()
    case=alice.post('/v1/cases',json={'title':'audit case'}).json()
    assert alice.get('/v1/research/resolve',params={'object_id':case['id']}).json()['href']=='/?case='+case['id']
    assert bob.get('/v1/research/resolve',params={'object_id':case['id']}).status_code==404
    sid=sample['sample']['id'];assert alice.get('/v1/research/resolve',params={'object_id':sid}).json()['href'].endswith(sid)
    assert bob.get('/v1/research/resolve',params={'object_id':sid}).status_code==404
    found=alice.get('/v1/research/audit-events',params={'q':'keyword-needle'}).json();assert found['items']
    summary=alice.get('/v1/research/audit-summary',params={'q':'keyword-needle','group_by':'action'}).json();assert summary['total']==len(found['items']) and summary['groups']
    text=alice.get('/v1/research/audit-events/export',params={'q':'keyword-needle','format':'log'});assert text.status_code==200 and 'INFO' in text.text and 'keyword-needle' in text.text
    assert bob.get('/v1/research/operations/review.sample/'+sid).status_code==404
    assert alice.get('/v1/research/operations/review.sample/'+sid).json()['body']['id']==sid


def test_historical_sync_is_idempotent_owned_and_artifact_hash_checked(lab):
    source=create(lab);directory=lab.store.root.parent.parent/'reports'/uid('trial');directory.mkdir(parents=True)
    summary=dict(flow_id='fixture-flow',status='awaiting_human_review',model='fixture',qa_success=0,qa_requests=0)
    for name,value in [('summary.json',summary),('execution.json',dict(sources=[source['sample']['id']],started_at=now())),('recovery.json',dict(candidate_ids=[],batches=[])),('request-ledger.json',[])]:
        (directory/name).write_text(dumps(value),encoding='utf-8')
    (directory/'REPORT.md').write_text('# Actual fixture',encoding='utf-8');ops=Operations(lab.store)
    with pytest.raises(KeyError):ops.import_trial('bob',directory)
    first=ops.import_trial('alice',directory);assert first['historical_sync'] and first['name']=='fixture · 1个初始样本试跑'
    assert ops.import_trial('alice',directory)==first
    assert ops.artifact('alice','fixture-flow','REPORT.md').is_file()
    with pytest.raises(KeyError):ops.artifact('bob','fixture-flow','REPORT.md')
    with pytest.raises(KeyError):ops.artifact('alice','fixture-flow','../cases-before.sqlite3')
    (directory/'REPORT.md').write_text('tampered',encoding='utf-8')
    with pytest.raises(ValueError):ops.artifact('alice','fixture-flow','REPORT.md')
