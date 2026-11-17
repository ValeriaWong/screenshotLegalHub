import copy
import io
import json
import sqlite3
import pytest
from PIL import Image
from test_research_products import lab,create,content,drain,prompt,human
from test_accounts_ingestion import accounts
from screenshotlegal.research.contracts import *
from screenshotlegal.research.store import Store,Conflict
from screenshotlegal.research import audit
from screenshotlegal.research.geometry import canonical
from screenshotlegal.research.gateway import evaluation_input

def manifest(lab,sid):
    return lab.store.get('review.manifest',lab.review.sample('alice',sid)['published_manifest'],'alice')

def original(lab):
    buf=io.BytesIO();Image.new('RGB',(800,600),'red').save(buf,format='PNG');data=buf.getvalue();sha=digest(data)
    asset=dict(id=sha,path='originals/'+sha+'.png',sha256=sha,width=800,height=600,mime_type='image/png')
    file=lab.store.root/asset['path'];file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
    with lab.store.tx() as db:lab.store.put('review.asset',asset,'alice',db,immutable=True)
    return asset

def test_audit_is_atomic_append_only_scoped_and_restart_safe(lab,monkeypatch):
    saved=create(lab);sid=saved['sample']['id']
    events=audit.query(lab.store,'alice',object_id=sid)['items']
    assert any(e['action']=='review.revision.created' for e in events)
    assert audit.query(lab.store,'bob')['items']==[]
    with lab.store.read() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM audit_events')
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE audit_events SET reason='modified'")
    before=lab.review.revision('alice',sid,1)
    reopened=Store(lab.store.root.parent);count=audit.summary(reopened,'alice')['total']
    Store(lab.store.root.parent)
    assert audit.summary(reopened,'alice')['total']==count
    assert reopened.get('review.revision',sid+':1','alice')==before
    emit=audit.emit
    def fail(db,owner,action,*args,**kw):
        if action=='review.revision.created':raise RuntimeError('audit storage failed')
        return emit(db,owner,action,*args,**kw)
    monkeypatch.setattr(audit,'emit',fail)
    with pytest.raises(RuntimeError):create(lab,content(title='must rollback'))
    assert len(lab.review.list_samples('alice'))==1
    assert audit.summary(lab.store,'alice')['outcomes']['rejected']>=1

def test_audit_pagination_redaction_and_object_context(lab):
    for i in range(6):create(lab,content(title=str(i)))
    first=audit.query(lab.store,'alice',limit=4)
    second=audit.query(lab.store,'alice',limit=4,cursor=first['next_cursor'])
    assert not {e['id'] for e in first['items']} & {e['id'] for e in second['items']}
    with lab.store.tx() as db:
        audit.emit(db,'alice','settings.changed','model','m',changes={'api_key':'SECRET','encrypted_api_key':'CIPHER','ordinary':1},event_key='settings')
        audit.emit(db,'alice','settings.changed','model','m',event_key='settings')
    rows=audit.query(lab.store,'alice',action='settings.changed')['items']
    assert len(rows)==1 and rows[0]['changes']['api_key']=='[redacted]'
    assert 'SECRET' not in dumps(rows) and 'CIPHER' not in dumps(rows)

async def test_original_image_is_reviewed_and_evaluated_without_placeholder(lab):
    asset=original(lab)
    saved=create(lab,content(kind='original',original_assets=[asset],messages=[],questions=[dict(id='q1',question='图中内容？')]))
    sid=saved['sample']['id'];await drain(lab)
    m=manifest(lab,sid)
    assert m['visual_role']=='original' and m['pages'][0]['sha256']==asset['sha256']
    assert m['pages'][0]['boxes']==[] and m['validation']['unannotated']
    human(lab,sid)
    release=lab.review.create_release('alice',ReleaseCreate(name='original',sample_ids=[sid],idempotency_key='release'))
    entry=release['entries'][0]
    assert evaluation_input(entry,entry['revision']['content']['questions'][0],'image')['images'][0]['sha256']==asset['sha256']
    assert entry['binding']['asset_hashes']==[asset['sha256']]
    events=audit.query(lab.store,'alice',object_id=sid)['items']
    assert any(e['action']=='review.release.created' for e in events)

async def test_visual_pass_requires_explicit_current_image_and_gold_reconfirmation(lab):
    saved=create(lab,content(questions=[dict(id='q1',question='金额多少',answer='100',gold=True)]));sid=saved['sample']['id']
    with pytest.raises(Conflict):lab.review.quality('alice',sid,QualitySave(revision=1,verdict='pass',idempotency_key='too-early'))
    await drain(lab);m=manifest(lab,sid)
    with pytest.raises(Conflict):lab.review.quality('alice',sid,QualitySave(revision=1,verdict='pass',manifest_id='old',idempotency_key='old'))
    lab.review.quality('alice',sid,QualitySave(revision=1,verdict='pass',manifest_id=m['id'],idempotency_key='no-gold-confirm'))
    with pytest.raises(Conflict,match='金标'):lab.review.create_release('alice',ReleaseCreate(name='bad',sample_ids=[sid],idempotency_key='bad'))
    human(lab,sid)
    release=lab.review.create_release('alice',ReleaseCreate(name='good',sample_ids=[sid],idempotency_key='good'))
    assert release['entries'][0]['gold_certifications']
    changed=copy.deepcopy(saved['revision']['content']);changed['questions'][0]['question']='付款日期是哪天'
    edit=lab.review.edit('alice',sid,SampleEdit(content=changed,expected_revision=1,note='new question',idempotency_key='question'))
    assert not edit['revision']['content']['questions'][0]['gold']
    assert edit['revision']['invalidated_gold']==['q1']
    with pytest.raises(Conflict):lab.review.create_release('alice',ReleaseCreate(name='stale',sample_ids=[sid],idempotency_key='stale'))
    assert lab.review.release('alice',release['id'])==release

async def test_overlapping_frames_and_unreadable_font_fail_without_losing_text(lab):
    value=content(messages=[dict(id='a',text='第一条消息'),dict(id='b',text='第二条消息')],questions=[])
    saved=create(lab,value);sid=saved['sample']['id'];await drain(lab);old=manifest(lab,sid)
    boxes=canonical(old['pages']);boxes[0]['boxes'][1]['bbox']=boxes[0]['boxes'][0]['bbox'].copy()
    edited=lab.review.edit('alice',sid,SampleEdit(content=value,expected_revision=1,note='overlap',layout=boxes,coordinates_unlocked=True,layout_manifest_id=old['id'],idempotency_key='overlap'))
    await drain(lab)
    assert lab.store.job(edited['job_id'],'alice')['status']=='failed'
    assert manifest(lab,sid)['id']==old['id']
    assert lab.review.revision('alice',sid,2)['content']['messages']==value.model_dump()['messages']

async def test_visual_quality_sends_pixels_and_comparison_never_pools_protocols(lab,monkeypatch):
    saved=create(lab);sid=saved['sample']['id'];await drain(lab);m=manifest(lab,sid);p=prompt(lab,'review');sent=[]
    async def fake(owner,model,messages,purpose,request_id):
        sent.append(messages);return dict(raw=dumps(dict(verdict='pass',score=90,findings='ok')),demo=False,usage=None,latency_ms=1)
    monkeypatch.setattr(lab.gateway,'call',fake)
    for coverage in ['text','visual']:
        lab.review.queue_quality('alice',sid,QualityRun(revision=1,prompt_id=p['id'],model_id='demo',coverage=coverage,manifest_id=m['id'] if coverage=='visual' else None,idempotency_key=coverage),lab.gateway.freeze('alice','demo'))
    await drain(lab)
    assert isinstance(sent[0][1]['content'],str)
    assert any(part['type']=='image_url' for part in sent[1][1]['content'])
    groups=[g for g in lab.review.comparison('alice') if g['model_scored']]
    assert len(groups)==2 and len({g['protocol_id'] for g in groups})==2
    changed=content(title='revised')
    lab.review.edit('alice',sid,SampleEdit(content=changed,expected_revision=1,note='repair',idempotency_key='repair'))
    groups=lab.review.comparison('alice')
    assert any(g['stage']=='initial' and g['model_mean']==90 for g in groups)
    assert any(g['stage']=='revised' and g['model_mean'] is None for g in groups)

async def test_feedback_scope_processing_cas_and_frozen_validation_target(lab):
    source=create(lab);sid=source['sample']['id'];p=prompt(lab)
    local=lab.review.comment('alice',sid,CommentSave(revision=1,body='一次性问题',idempotency_key='local'))
    durable=lab.review.comment('alice',sid,CommentSave(revision=1,body='长期约束',applicability='source',idempotency_key='durable'))
    lab.review.edit('alice',sid,SampleEdit(content=content(title='fixed'),expected_revision=1,note='fixed',idempotency_key='fix'))
    assert [c['id'] for c in lab.studio.feedback('alice',sid)]==[durable['id']]
    batch=lab.studio.create_batch('alice',BatchCreate(name='next',dataset='g',source_sample_id=sid,source_revision=2,prompt_id=p['id'],feedback_ids=[durable['id']],idempotency_key='batch'))
    await drain(lab);candidate=lab.studio.batches('alice')[0]['sample_ids'][0]
    action=CommentProcess(status='resolved',reason='已检查新候选',candidate_sample_id=candidate,candidate_revision=1,idempotency_key='resolve')
    event=lab.review.process_comment('alice',sid,durable['id'],action)
    assert event['verification']=='human' and event['candidate_content_hash']
    with pytest.raises(Conflict):lab.review.process_comment('alice',sid,durable['id'],action.model_copy(update={'idempotency_key':'conflict'}))
    assert lab.studio.feedback('alice',sid)==[]
    assert lab.store.get('studio.batch',batch['id'],'alice')['review_feedback'][0]['body']=='长期约束'
    assert local['id']!=durable['id']

def test_audit_api_permissions_and_rejected_requests(accounts):
    _,admin,alice,bob=accounts
    payload=dict(dataset='audit',content=content().model_dump(),note='initial',idempotency_key='audit')
    saved=alice.post('/v1/review/samples',json=payload).json();sid=saved['sample']['id']
    assert alice.post('/v1/review/samples',json=payload).status_code==201
    events=alice.get('/v1/research/audit-events',params={'object_id':sid}).json()['items']
    assert sum(e['action']=='review.revision.created' for e in events)==1
    event=events[0]['id']
    assert alice.get('/v1/research/audit-events/'+event).status_code==200
    assert bob.get('/v1/research/audit-events/'+event).status_code==404
    assert bob.get('/v1/research/audit-events').json()['items']==[]
    assert alice.put('/v1/review/samples/'+sid,json=dict(content=content().model_dump(),expected_revision=99,note='conflict',idempotency_key='conflict')).status_code==409
    assert alice.get('/v1/research/audit-summary',params={'outcome':'rejected'}).json()['total']>=1
    assert alice.get('/v1/research/audit-events/export').status_code==200


def test_case_and_model_operations_use_durable_owner_outbox(accounts):
    workspace,admin,alice,bob=accounts
    from test_accounts_ingestion import model,KEY
    saved=model(alice)
    first=alice.get('/v1/research/audit-events',params={'product':'settings'}).json()['items']
    assert any(e['action']=='model.created' and e['object_id']==saved['id'] for e in first)
    assert KEY not in dumps(first) and 'ciphertext' not in dumps(first)
    before=len(first)
    assert len(alice.get('/v1/research/audit-events',params={'product':'settings'}).json()['items'])==before
    assert bob.get('/v1/research/audit-events',params={'product':'settings'}).json()['items']==[]
    assert alice.delete('/v1/settings/models/'+saved['id']).status_code==200
    assert any(e['action']=='model.deleted' for e in alice.get('/v1/research/audit-events',params={'product':'settings'}).json()['items'])
    case=alice.post('/v1/cases',json={'title':'audit case'}).json()
    snapshot=alice.get('/v1/cases/'+case['id']+'/workbench').json()
    update=alice.put('/v1/cases/'+case['id']+'/workbench',json={'title':'edited audit case','summary':'summary','notes':'notes','expected_revision':snapshot['case']['revision']})
    assert update.status_code==200
    events=alice.get('/v1/research/audit-events',params={'product':'workbench','object_id':case['id']}).json()['items']
    assert events and events[0]['changes']['title']['after']=='edited audit case'
    primary=workspace.operation_events(alice.get('/v1/auth/me').json()['id'])
    assert any(e['object_id']==case['id'] and e['action']=='case.edited' for e in primary)


def test_upgrade_existing_sqlite_keeps_legacy_bytes_and_does_not_invent_actor(tmp_path):
    folder=tmp_path/'research';folder.mkdir();file=folder/'research.sqlite3'
    db=sqlite3.connect(file)
    db.execute('CREATE TABLE records (kind TEXT,id TEXT,owner TEXT,body TEXT,PRIMARY KEY(kind,id,owner))')
    body='{"id":"old","revision":1,"title":"legacy"}'
    db.execute('INSERT INTO records VALUES (?,?,?,?)',('review.sample','old','alice',body));db.commit();db.close()
    store=Store(tmp_path)
    with store.read() as db:assert db.execute("SELECT body FROM records WHERE id='old'").fetchone()[0]==body
    event=audit.query(store,'alice')['items'][0]
    assert event['action']=='migration_snapshot' and event['actor_id']=='unknown' and event['context']['binding']=='legacy_unbound'
    Store(tmp_path)
    assert audit.summary(store,'alice')['total']==1


def test_audit_chronological_cursor_and_timezone_filter(lab):
    with lab.store.tx() as db:
        audit.emit(db,'clock','new','test','new',occurred_at='2026-10-24T01:00:00+00:00')
        audit.emit(db,'clock','old','test','old',occurred_at='2026-10-23T01:00:00+00:00')
    first=audit.query(lab.store,'clock',limit=1)
    assert first['items'][0]['object_id']=='new'
    second=audit.query(lab.store,'clock',limit=1,cursor=first['next_cursor'])
    assert second['items'][0]['object_id']=='old'
    assert audit.summary(lab.store,'clock',since='2026-10-24T08:00:00+08:00')['total']==1


def test_same_v3_source_variants_share_only_applicable_feedback(lab):
    a=create(lab,content(source_text='',metadata={'source_manifest':'datasets/v3.0.0/calibration/cases/topic/base/messages.jsonl'}))
    b=create(lab,content(source_text='',metadata={'source_manifest':'datasets/v3.0.0/calibration/cases/topic/variant/messages.jsonl'}))
    c=create(lab,content(source_text='',metadata={'source_manifest':'datasets/v3.0.0/calibration/cases/other/base/messages.jsonl'}))
    note=lab.review.comment('alice',a['sample']['id'],CommentSave(revision=1,body='同源约束',applicability='source',idempotency_key='note'))
    assert [q['id'] for q in lab.studio.feedback('alice',b['sample']['id'])]==[note['id']]
    assert lab.studio.feedback('alice',c['sample']['id'])==[]


async def test_quality_failure_is_visible_in_comparison_and_has_parent_event(lab,monkeypatch):
    from screenshotlegal.research.gateway import ModelFailure
    saved=create(lab);await drain(lab);p=prompt(lab,'review')
    async def fail(*args):raise ModelFailure('rate_limit','limited',True)
    monkeypatch.setattr(lab.gateway,'call',fail)
    job=lab.review.queue_quality('alice',saved['sample']['id'],QualityRun(revision=1,prompt_id=p['id'],model_id='demo',idempotency_key='fail'),lab.gateway.freeze('alice','demo'))
    await drain(lab)
    group=next(g for g in lab.review.comparison('alice') if g['protocol_id']!='unreviewed')
    assert group['quality_attempts']==1 and group['failed_attempts']==1 and group['model_mean'] is None
    events=audit.query(lab.store,'alice',object_id=saved['sample']['id'])['items']
    failure=next(e for e in events if e['outcome']=='failed')
    assert failure['parent_event_id']==job['audit_event_id']
