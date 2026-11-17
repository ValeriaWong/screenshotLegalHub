import copy
import json
import pytest
from pydantic import ValidationError
from test_research_products import lab, create, edit, content, drain, prompt, human
from test_accounts_ingestion import accounts
from screenshotlegal.research.contracts import SampleEdit, CommentSave, BatchCreate, uid
from screenshotlegal.research.geometry import canonical
from screenshotlegal.research.store import Conflict


def manifest(lab, sid):
    sample=lab.review.sample('alice',sid)
    return lab.store.get('review.manifest',sample['published_manifest'],'alice')


async def test_text_save_keeps_locked_pixel_regions_and_manual_edits_require_unlock(lab):
    first=create(lab)
    await drain(lab)
    sid=first['sample']['id']
    original=manifest(lab,sid)
    layout=canonical(original['pages'])
    moved=copy.deepcopy(layout)
    moved[0]['boxes'][0]['bbox'][0]+=12
    request=dict(content=content(),expected_revision=1,note='调整消息框',layout=moved,layout_manifest_id=original['id'],idempotency_key='move')
    with pytest.raises(Conflict,match='锁定'):
        lab.review.edit('alice',sid,SampleEdit(**request))
    assert lab.review.sample('alice',sid)['revision']==1
    with pytest.raises(Conflict,match='图片版本'):
        lab.review.edit('alice',sid,SampleEdit(**dict(request,coordinates_unlocked=True,layout_manifest_id='stale')))
    changed=lab.review.edit('alice',sid,SampleEdit(**request,coordinates_unlocked=True))
    await drain(lab)
    m=manifest(lab,sid)
    assert m['revision']==2 and canonical(m['pages'])==moved
    assert changed['revision']['layout_diff']['after']==moved
    updated=content(messages=[dict(id='m1',speaker='A',text='纠正后的消息')])
    lab.review.edit('alice',sid,SampleEdit(content=updated,expected_revision=2,note='只改文本',idempotency_key='text'))
    await drain(lab)
    latest=manifest(lab,sid)
    assert canonical(latest['pages'])==moved
    assert latest['pages'][0]['sha256']!=m['pages'][0]['sha256']


async def test_invalid_or_replaced_message_geometry_is_rejected(lab):
    saved=create(lab)
    await drain(lab)
    m=manifest(lab,saved['sample']['id'])
    pages=canonical(m['pages'])
    pages[0]['boxes'][0]['bbox'][0]=-1
    with pytest.raises(ValidationError):
        SampleEdit(content=content(),expected_revision=1,note='bad',layout=pages,idempotency_key='bad')
    pages=canonical(m['pages']);pages[0]['boxes'][0]['message_id']='unknown'
    with pytest.raises(Conflict,match='消息映射'):
        lab.review.edit('alice',saved['sample']['id'],SampleEdit(content=content(),expected_revision=1,note='bad map',layout=pages,coordinates_unlocked=True,layout_manifest_id=m['id'],idempotency_key='bad-map'))


async def test_too_small_frame_retains_text_and_allows_recovery_against_previous_image(lab):
    value=content(messages=[dict(id='m1',speaker='A',text='长句'*100)])
    saved=create(lab,value)
    await drain(lab)
    sid=saved['sample']['id'];old=manifest(lab,sid)
    tiny=canonical(old['pages']);tiny[0]['boxes'][0]['bbox']=[30,100,78,148]
    bad=lab.review.edit('alice',sid,SampleEdit(content=value,expected_revision=1,note='缩小坐标',layout=tiny,coordinates_unlocked=True,layout_manifest_id=old['id'],idempotency_key='small'))
    await drain(lab)
    failed=lab.store.job(bad['job_id'],'alice')
    assert failed['status']=='failed' and failed['error']['category']=='render_layout'
    assert manifest(lab,sid)['id']==old['id']
    assert lab.review.revision('alice',sid,2)['content']['messages'][0]['text']==value.messages[0].text
    lab.review.edit('alice',sid,SampleEdit(content=value,expected_revision=2,note='扩大框恢复',layout=canonical(old['pages']),coordinates_unlocked=True,layout_manifest_id=old['id'],idempotency_key='recover'))
    await drain(lab)
    assert manifest(lab,sid)['revision']==3


async def test_comment_only_has_context_and_history_without_revision_or_render_side_effect(lab):
    saved=create(lab)
    await drain(lab)
    sid=saved['sample']['id'];m=manifest(lab,sid)
    human(lab,sid)
    jobs=lab.store.jobs('alice')
    payload=CommentSave(revision=1,message_id='m1',body='下一轮避免补造日期，语气自然一些',manifest_id=m['id'],page=1,bbox=m['pages'][0]['boxes'][0]['bbox'],idempotency_key='comment')
    c=lab.review.comment('alice',sid,payload)
    assert lab.review.comment('alice',sid,payload)==c
    assert lab.review.sample('alice',sid)['revision']==1 and lab.review.sample('alice',sid)['status']=='approved'
    assert len(lab.store.jobs('alice'))==len(jobs)
    assert c['message_snapshot']['text']==saved['revision']['content']['messages'][0]['text']
    q=lab.store.get('review.quality',c['quality_id'],'alice')
    assert q['method']=='comment' and q['suggestions']==payload.body
    amended=lab.review.comment('alice',sid,CommentSave(revision=1,message_id='m1',body='修订后的评论',supersedes=c['id'],idempotency_key='amend'))
    assert len(lab.review.detail('alice',sid)['comments'])==2
    assert [v['id'] for v in lab.review.feedback('alice',[sid])]==[amended['id']]
    with pytest.raises(KeyError):
        lab.review.comment('bob',sid,payload)
    with pytest.raises(ValueError):
        lab.review.comment('alice',sid,CommentSave(revision=1,message_id='missing',body='bad',idempotency_key='missing'))


async def test_generation_uses_frozen_feedback_from_same_source_candidates(lab,monkeypatch):
    source=create(lab);p=prompt(lab)
    args=dict(name='first',dataset='generated',source_sample_id=source['sample']['id'],source_revision=1,prompt_id=p['id'])
    first=lab.studio.create_batch('alice',BatchCreate(**args,idempotency_key='first'))
    await drain(lab)
    candidate=lab.store.get('studio.batch',first['id'],'alice')['sample_ids'][0]
    c=lab.review.comment('alice',candidate,CommentSave(revision=1,message_id='m1',body='修订反馈：不要加入未知分钟',idempotency_key='feedback'))
    lab.review.comment('alice',candidate,CommentSave(revision=1,body='这条不用于生成',use_for_generation=False,idempotency_key='private-note'))
    second=lab.studio.create_batch('alice',BatchCreate(**dict(args,name='second'),idempotency_key='second'))
    assert [f['id'] for f in second['review_feedback']]==[c['id']]
    lab.review.comment('alice',candidate,CommentSave(revision=1,message_id='m1',body='稍后新意见',supersedes=c['id'],idempotency_key='later'))
    sent=[]
    async def fake(owner,model,messages,purpose,request_id):
        sent.append(messages)
        return dict(raw='DEMO',demo=True,latency_ms=1,usage=None)
    monkeypatch.setattr(lab.gateway,'call',fake)
    await drain(lab)
    feedback=json.loads(sent[0][1]['content'])['review_feedback']
    assert feedback[0]['body']==c['body'] and '稍后新意见' not in json.dumps(feedback,ensure_ascii=False)
    skipped=lab.studio.create_batch('alice',BatchCreate(**dict(args,name='skip'),use_review_feedback=False,idempotency_key='skip'))
    assert skipped['review_feedback']==[]


def test_judgment_presence_missing_placeholder_and_comment_api_permissions(accounts):
    _,admin,alice,bob=accounts
    payload=dict(dataset='canvas',content=content().model_dump(),note='initial',idempotency_key='create')
    response=alice.post('/v1/review/samples',json=payload)
    assert response.status_code==201
    sid=response.json()['sample']['id']
    judgment=alice.get('/v1/review/samples/'+sid+'/judgment').json()
    assert judgment['available'] and judgment['text']==payload['content']['source_text']
    no_source=alice.post('/v1/review/samples',json=dict(payload,content=content(source_text='').model_dump(),idempotency_key='empty')).json()['sample']['id']
    assert alice.get('/v1/review/samples/'+no_source+'/judgment').json()['available'] is False
    assert bob.get('/v1/review/samples/'+sid+'/judgment').status_code==404
    c=alice.post('/v1/review/samples/'+sid+'/comments',json=dict(revision=1,message_id='m1',body='仅添加评论',idempotency_key='api-comment'))
    assert c.status_code==201,c.text
    assert alice.get('/v1/review/samples/'+sid).json()['sample']['revision']==1
    assert alice.get('/v1/studio/feedback',params={'source_sample_id':sid}).json()[0]['id']==c.json()['id']
    assert bob.post('/v1/review/samples/'+sid+'/comments',json=dict(revision=1,body='forbidden',idempotency_key='bad')).status_code==404
