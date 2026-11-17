import asyncio,copy,json
import httpx
import pytest
from pydantic import ValidationError
from screenshotlegal.research import audit
from screenshotlegal.research.contracts import *
from screenshotlegal.research.gateway import Gateway,ModelFailure
from screenshotlegal.research.store import Conflict
from screenshotlegal.research.renderer import wrap,font,layout,fixed_layout,render_png,RenderLayoutError
from screenshotlegal.research.quality_inputs import VERSION
from test_research_products import lab,create,content,prompt,drain,human
from test_research_reliability import original,manifest
from test_operations_observability import configuration

@pytest.mark.parametrize('coverage',['text','visual','multimodal'])
async def test_quality_scope_is_the_frozen_reviewed_manifest_not_source_inventory(lab,monkeypatch,coverage):
    asset=original(lab);saved=create(lab,content(original_assets=[asset]*8));sid=saved['sample']['id'];await drain(lab)
    m=manifest(lab,sid);p=prompt(lab,'review');sent=[]
    async def reply(owner,model,messages,purpose,request_id):
        sent.append(messages);return dict(raw=dumps(dict(verdict='revise',score=70)),demo=False,usage=None,latency_ms=1)
    monkeypatch.setattr(lab.gateway,'call',reply)
    j=lab.review.queue_quality('alice',sid,QualityRun(revision=1,prompt_id=p['id'],model_id='demo',coverage=coverage,manifest_id=m['id'] if coverage!='text' else None,idempotency_key=coverage),lab.gateway.freeze('alice','demo'))
    # A later source edit cannot change the queued input or re-label the inspected revision.
    lab.review.edit('alice',sid,SampleEdit(content=content(title='changed later'),expected_revision=1,note='later',idempotency_key='later'))
    await drain(lab)
    body=sent[0][1]['content'];task=json.loads(body if isinstance(body,str) else body[0]['text'])
    assert task['input_contract_version']==VERSION and task['reviewed_object']['revision']==1
    assert task['source_context']['source_asset_count']==8 and 'original_assets' not in task['content']
    assert task['reviewed_object']['expected_pages']==(0 if coverage=='text' else 1)
    if coverage!='text':
        assert task['reviewed_object']['visual_role']=='synthetic_render'
        assert task['reviewed_object']['pages'][0]['sha256']==m['pages'][0]['sha256']
        assert len([part for part in body if part['type']=='image_url'])==1
    assert ('messages' in task['content'])==(coverage!='visual')
    q=lab.store.get('review.quality',j['id']+':quality','alice')
    assert q['protocol']['input_contract_version']==VERSION and q['reviewed_object']==task['reviewed_object']

async def test_original_review_keeps_all_inspected_original_pages(lab,monkeypatch):
    a=original(lab);saved=create(lab,content(kind='original',original_assets=[a,a]));sid=saved['sample']['id'];await drain(lab);m=manifest(lab,sid);p=prompt(lab,'review');sent=[]
    async def reply(*args):sent.append(args[2]);return dict(raw=dumps(dict(verdict='pending')),demo=False,usage=None,latency_ms=1)
    monkeypatch.setattr(lab.gateway,'call',reply)
    lab.review.queue_quality('alice',sid,QualityRun(revision=1,prompt_id=p['id'],model_id='demo',coverage='visual',manifest_id=m['id'],idempotency_key='q'),lab.gateway.freeze('alice','demo'));await drain(lab)
    parts=sent[0][1]['content'];scope=json.loads(parts[0]['text'])['reviewed_object']
    assert scope['visual_role']=='original' and scope['expected_pages']==2
    assert len([p for p in parts if p['type']=='image_url'])==2

async def test_pending_legacy_quality_keeps_its_protocol_and_serializer(lab,monkeypatch):
    saved=create(lab);sid=saved['sample']['id'];await drain(lab);m=manifest(lab,sid);p=prompt(lab,'review')
    j=lab.review.queue_quality('alice',sid,QualityRun(revision=1,prompt_id=p['id'],model_id='demo',coverage='multimodal',manifest_id=m['id'],idempotency_key='old'),lab.gateway.freeze('alice','demo'))
    with lab.store.tx() as db:
        job=lab.store.job(j['id'],'alice',db);job['payload'].pop('input_contract_version');job['payload'].pop('review_input');job['payload']['protocol']={'method':'model','legacy':True};job['payload']['protocol_id']='old-protocol';lab.store.save_job(db,job)
    sent=[]
    async def reply(*args):sent.append(args[2]);return dict(raw=dumps(dict(verdict='pending')),demo=False,usage=None,latency_ms=1)
    monkeypatch.setattr(lab.gateway,'call',reply);await drain(lab)
    assert 'context' in json.loads(sent[0][1]['content'][0]['text'])
    q=lab.store.get('review.quality',j['id']+':quality','alice');assert q['protocol_id']=='old-protocol' and q['input_contract_version']=='quality-input.v1'
    assert lab.review.detail('alice',sid)['quality'][0]['input_scope_status']=='legacy_scope_ambiguous'

async def test_worker_call_audit_is_scoped_by_each_model_id_and_original_operation(lab,workspace,monkeypatch):
    config=workspace.preferences('alice').save_model(configuration());g=Gateway(lab.store,workspace);lab.worker.gateway=g
    saved=create(lab);await drain(lab);p=prompt(lab,'review');calls=[];client=httpx.AsyncClient
    def reply(req):
        calls.append(req)
        if len(calls)==2:return httpx.Response(429)
        if len(calls)==3:raise httpx.ReadTimeout('no response')
        return httpx.Response(200,headers={'x-request-id':'provider-scope'},json={'choices':[{'message':{'content':'{"verdict":"pending"}'}}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(reply),**kw))
    ctx=audit.context.set(dict(request_id='http-operation',correlation_id='flow-scope'))
    try:
        jobs=[lab.review.queue_quality('alice',saved['sample']['id'],QualityRun(revision=1,prompt_id=p['id'],model_id=config.id,idempotency_key=str(i)),g.freeze('alice',config.id)) for i in range(3)]
    finally:audit.context.reset(ctx)
    await drain(lab)
    ids=[]
    for j,status in zip(jobs,['completed','failed','unknown']):
        job=lab.store.job(j['id'],'alice');rid=job['checkpoints']['request:response']['request_id'];ids.append(rid)
        found=audit.query(lab.store,'alice',request_id=rid)['items']
        assert len([e for e in found if e['object_type']=='evaluation.request'])==2
        assert all(e['context']['model_call_id']==rid and e['request_id']=='http-operation' for e in found)
        assert lab.store.get('evaluation.request',rid,'alice')['status']==status
        assert audit.summary(lab.store,'alice',request_id=rid)['total']==len(found)
        assert not audit.query(lab.store,'bob',request_id=rid)['items']
        assert any(e['outcome']=={'completed':'success','failed':'failed','unknown':'unknown'}[status] for e in found)
    assert len(set(ids))==3 and len(calls)==3
    assert audit.query(lab.store,'alice',request_id='provider-scope')['items']
    assert audit.context.get().get('model_call_id') is None

def test_historical_request_lookup_works_without_rewriting_events(lab):
    with lab.store.tx() as db:
        audit.emit(db,'alice','evaluation.request.created','evaluation.request','old-call',details={},event_key='old')
        before=db.execute('select * from audit_events order by seq').fetchall()
    assert len(audit.query(lab.store,'alice',request_id='old-call')['items'])==1
    assert audit.summary(lab.store,'alice',request_id='old-call',q='evaluation.request')['total']==1
    with lab.store.read() as db:assert [tuple(x) for x in db.execute('select * from audit_events order by seq')]==[tuple(x) for x in before]

async def test_wait_policy_freezes_and_total_timeout_is_unknown_without_replay(lab,workspace,monkeypatch):
    pref=workspace.preferences('alice');cfg=pref.save_model(configuration(request_timeout_seconds=7,request_total_timeout_seconds=1));g=Gateway(lab.store,workspace);snap=g.freeze('alice',cfg.id)
    pref.save_model(configuration(request_timeout_seconds=30),cfg.id)
    assert snap['timeout_policy']==dict(connect=7,read=7,write=7,pool=7,total=1)
    calls=[];timeouts=[];client=httpx.AsyncClient
    async def wait(req):calls.append(req);await asyncio.sleep(5);raise AssertionError('not cancelled')
    def make(**kw):timeouts.append(kw['timeout']);return client(transport=httpx.MockTransport(wait),**kw)
    monkeypatch.setattr(httpx,'AsyncClient',make)
    with pytest.raises(ModelFailure) as error:await g.call('alice',snap,[],'probe','total-call')
    row=lab.store.get('evaluation.request','total-call','alice')
    assert error.value.unknown and row['status']=='unknown' and row['error']['evidence']['timeout_phase']=='total'
    assert row['error']['evidence']['usage'] is None and row['error']['evidence']['latency_ms']>=900
    assert len(calls)==1 and timeouts[0].read==7 and 'max_tokens' not in snap['parameters']
    for args in [dict(request_timeout_seconds=0),dict(request_total_timeout_seconds=0)]:
        with pytest.raises(ValidationError):configuration(**args)

def test_word_boundaries_long_tokens_and_multiline_headers():
    text="Srimila says it leaves everything to amma before she replies. £147,000 is disputed."
    f=font(24);lines=wrap(text,f,320)
    assert ' '.join(lines).split()==text.split() and all(f.getlength(x)<=320 for x in lines)
    punctuation=wrap('foo before. bar',f,f.getlength('foo before'))
    assert not any(x.startswith('.') for x in punctuation)
    url='https://example.test/'+('abcdef'*40);chunks=wrap(url,f,120)
    assert ''.join(chunks)==url and all(f.getlength(x)<=120 for x in chunks)
    c=content(title='Long scenario title '*20,messages=[dict(id='m1',speaker='Sender and source context '*4,timestamp='2026-10-24 10:49',text='Read this before replying.')]).model_dump();params=RenderParams().model_dump()
    bs=layout(c,params)[0];assert len(bs[0]['header_lines'])>1
    assert ''.join(''.join(bs[0]['header_lines']).split())==''.join((c['messages'][0]['speaker']+' · '+c['messages'][0]['timestamp']).split())
    assert render_png(c,params,bs,1).startswith(b'\x89PNG')
    fixed=[dict(page=1,width=760,height=1100,boxes=[dict(message_id='m1',bbox=[30,400,730,700])])]
    page=fixed_layout(c,params,fixed)[0];assert page['blocks'][0]['bbox']==[30,400,730,700]
    assert page['blocks'][0]['header_lines'][-1].endswith('10:49')
    with pytest.raises(RenderLayoutError):fixed_layout(c,params,[dict(page=1,width=760,height=1100,boxes=[dict(message_id='m1',bbox=[30,100,130,140])])])

async def test_legacy_render_job_and_checkpoint_keep_old_version(lab):
    saved=create(lab);sid=saved['sample']['id']
    with lab.store.tx() as db:
        j=lab.store.job(saved['job_id'],'alice',db);j['payload']['revision']['renderer_version']='pillow-chat.v3';lab.store.save_job(db,j)
    await drain(lab);old=manifest(lab,sid);assert old['renderer_version']=='pillow-chat.v3' and old['pages'][0]['render_policy']=='visual.v1'
    edit=lab.review.edit('alice',sid,SampleEdit(content=content(),expected_revision=1,note='explicit new view',idempotency_key='v4'));await drain(lab);new=manifest(lab,sid)
    assert new['renderer_version']=='pillow-chat.v4' and new['validation']['policy']=='visual.v2' and new['id']!=old['id']
    assert lab.store.get('review.manifest',old['id'],'alice')==old

async def test_explicit_renderer_upgrade_preserves_text_history_and_requires_review(lab):
    saved=create(lab,content(questions=[dict(id='q1',question='Which text?',answer='公開',gold=True,message_ids=['m1'])]));sid=saved['sample']['id']
    # Seed a legacy revision and its pending job in this isolated fixture only.
    with lab.store.tx() as db:
        old=lab.review.revision('alice',sid,1,db);old['renderer_version']='pillow-chat.v3'
        db.execute("UPDATE records SET body=? WHERE kind='review.revision' AND id=?",(dumps(old),old['id']))
        j=lab.store.job(saved['job_id'],'alice',db);j['payload']['revision']=old;lab.store.save_job(db,j)
    await drain(lab);old_image=manifest(lab,sid);human(lab,sid)
    released=lab.review.create_release('alice',ReleaseCreate(name='old release',sample_ids=[sid],idempotency_key='old-release'))
    before=lab.review.detail('alice',sid);payload=RendererUpgrade(expected_revision=1,idempotency_key='upgrade')
    upgraded=lab.review.upgrade_renderer('alice',sid,payload)
    assert upgraded['revision']['content']==old['content'] and upgraded['revision']['diff']=={}
    assert upgraded['sample']['revision']==2 and upgraded['sample']['status']=='needs_review'
    assert lab.review.upgrade_renderer('alice',sid,payload)==upgraded
    with pytest.raises(Conflict):lab.review.upgrade_renderer('alice',sid,RendererUpgrade(expected_revision=1,idempotency_key='stale'))
    with pytest.raises(KeyError):lab.review.upgrade_renderer('bob',sid,payload)
    await drain(lab);new=manifest(lab,sid)
    assert new['renderer_version']==RENDERER and new['id']!=old_image['id']
    assert lab.review.revision('alice',sid,1)==old and lab.store.get('review.manifest',old_image['id'],'alice')==old_image
    assert lab.review.release('alice',released['id'])==released
    after=lab.review.detail('alice',sid)
    assert after['gold_certifications']==before['gold_certifications'] and all(q['revision']==1 for q in after['gold_certifications'])
    with pytest.raises(Conflict):lab.review.create_release('alice',ReleaseCreate(name='not reviewed',sample_ids=[sid],idempotency_key='new-release'))
    with pytest.raises(Conflict):lab.review.upgrade_renderer('alice',sid,RendererUpgrade(expected_revision=2,idempotency_key='already'))
    asset=original(lab);raw=create(lab,content(kind='original',original_assets=[asset]));await drain(lab)
    with pytest.raises(Conflict):lab.review.upgrade_renderer('alice',raw['sample']['id'],RendererUpgrade(expected_revision=1,idempotency_key='raw'))
