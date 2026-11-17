import asyncio
import copy
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from pathlib import Path
import pytest
from screenshotlegal.research.contracts import *
from screenshotlegal.research.store import Store, Conflict
from screenshotlegal.research.review import ReviewDesk
from screenshotlegal.research.products import DataStudio, EvaluationLab
from screenshotlegal.research.gateway import Gateway, ModelFailure, evaluation_input, request_messages
from screenshotlegal.research.worker import Worker
from screenshotlegal.research.renderer import verified
from screenshotlegal.research.catalog import Catalog
from test_accounts_ingestion import accounts

@pytest.fixture
def lab(tmp_path):
    store=Store(tmp_path)
    review=ReviewDesk(store)
    gateway=Gateway(store,None)
    evaluation=EvaluationLab(store,review,gateway)
    studio=DataStudio(store,review,gateway)
    worker=Worker(store,review,gateway,evaluation)
    return SimpleNamespace(store=store,review=review,gateway=gateway,evaluation=evaluation,studio=studio,worker=worker)

def content(**changes):
    value=dict(title='候选聊天',source_text='PRIVATE SOURCE HIDDEN_ANSWER',category='chat',metadata={'hidden':'GOLD_SENTINEL'},
               messages=[dict(id='m1',speaker='A',text='公开的消息。')],
               questions=[dict(id='q1',question='公开题目',answer='GOLD_SENTINEL',gold=False,message_ids=['m1'])])
    value.update(changes)
    return Content.model_validate(value)

def create(lab, value=None):
    return lab.review.create('alice',SampleCreate(dataset='test',content=value or content(),note='初始导入',idempotency_key=uid('key')))

def edit(lab, saved, value=None, **changes):
    return lab.review.edit('alice',saved['sample']['id'],SampleEdit(content=value or content(title='纠正版'),expected_revision=saved['sample']['revision'],note='纠错意见',idempotency_key=uid('key'),**changes))

async def drain(lab):
    for _ in range(100):
        job=lab.store.claim()
        if not job:
            return
        await lab.worker.execute(job)
    raise AssertionError('queue did not drain')

def human(lab,sid,revision=1,verdict='pass',score=90,**kw):
    sample=lab.review.sample('alice',sid)
    kw.setdefault('review_scope','both' if sample.get('published_manifest') else 'text')
    if kw['review_scope']=='both':
        kw.setdefault('manifest_id',sample['published_manifest']);kw.setdefault('confirm_gold',True)
    return lab.review.quality('alice',sid,QualitySave(revision=revision,verdict=verdict,score=score,suggestions='核对消息',process='人工对照原文',idempotency_key=uid('key'),**kw))

async def release(lab, gold=False):
    saved=create(lab,content(questions=[dict(id='q1',question='公开题目',answer='GOLD_SENTINEL',gold=gold,message_ids=['m1']),
                                      dict(id='q2',question='无金标题目',answer='作者答案',gold=False)]))
    await drain(lab)
    human(lab,saved['sample']['id'])
    r=lab.review.create_release('alice',ReleaseCreate(name='冻结版本',sample_ids=[saved['sample']['id']],idempotency_key=uid('key')))
    return saved,r

def prompt(lab,purpose='studio'):
    return lab.review.save_prompt('alice',purpose,PromptSave(name='质量或生成',markdown='# Prompt\n约束',note='初版',expected_version=0,idempotency_key=uid('key')))

def test_revision_outbox_idempotency_and_conflict(lab):
    payload=SampleCreate(dataset='d',content=content(),note='import',idempotency_key='same')
    first=lab.review.create('alice',payload)
    assert lab.review.create('alice',payload)==first
    with pytest.raises(Conflict):
        lab.review.create('alice',payload.model_copy(update={'note':'different'}))
    second=edit(lab,first)
    with pytest.raises(Conflict):
        edit(lab,first)
    detail=lab.review.detail('alice',first['sample']['id'])
    assert len(detail['revisions'])==2 and len(detail['jobs'])==2
    assert detail['revision']['parent']==1 and detail['revision']['diff']['title']['before']=='候选聊天'
    assert detail['quality'][0]['method']=='correction' and detail['quality'][0]['suggestions']=='纠错意见'
    assert second['job_id']!=first['job_id']

def test_simultaneous_edit_keeps_one_winner(lab):
    saved=create(lab)
    def attempt(title):
        try:
            return edit(lab,saved,content(title=title))['sample']['revision']
        except Conflict:
            return 'conflict'
    with ThreadPoolExecutor(2) as executor:
        results=list(executor.map(attempt,['A','B']))
    assert sorted(map(str,results))==['2','conflict']

def test_server_drafts_have_cas_and_stale_base(lab):
    saved=create(lab); sid=saved['sample']['id']
    d=DraftSave(base_revision=1,expected_version=0,draft_id='draft',content={'content':content().model_dump()})
    row=lab.review.save_draft('alice',sid,d)
    assert row['version']==1
    with pytest.raises(Conflict):
        lab.review.save_draft('alice',sid,d)
    edit(lab,saved)
    with pytest.raises(Conflict):
        lab.review.save_draft('alice',sid,d.model_copy(update={'expected_version':1}))
    assert lab.store.get('review.draft',sid+':alice','alice')['content']==d.content

def test_quality_revision_history_and_comparison(lab):
    saved=create(lab); sid=saved['sample']['id']
    q=human(lab,sid,score=40,verdict='revise')
    amended=human(lab,sid,score=80,supersedes=q['id'])
    assert len(lab.review.detail('alice',sid)['quality'])==2
    assert lab.review.comparison('alice')[0]['human_mean']==80
    with pytest.raises(Conflict):
        human(lab,sid,score=100,supersedes=q['id'])
    edit(lab,saved)
    projection=next(g for g in lab.review.comparison('alice') if g['stage']=='revised')
    assert projection['human_mean'] is None and projection['reviewed_samples']==0 and projection['corrections']==1
    assert amended['supersedes']==q['id']

def test_prompt_markdown_is_append_only_and_scoped(lab):
    saved=create(lab)
    q=human(lab,saved['sample']['id'])
    p=prompt(lab)
    payload=PromptSave(name=p['name'],markdown='# v2',note='依据质量反馈纠正',expected_version=1,
                       feedback_ids=[q['id']],idempotency_key='v2')
    v2=lab.review.save_prompt('alice','studio',payload)
    assert v2['parent_id']==p['id'] and v2['version']==2
    assert lab.review.save_prompt('alice','studio',payload)==v2
    assert '# Prompt' in lab.review.prompt_markdown('alice','studio',p['name'])
    assert q['id'] in lab.review.prompt_markdown('alice','studio',p['name'])
    with pytest.raises(Conflict):
        lab.review.save_prompt('alice','studio',payload.model_copy(update={'idempotency_key':'other'}))
    assert lab.review.prompts('alice','review')==[]
    with pytest.raises(KeyError):
        lab.review.prompt('bob','studio',p['id'])

async def test_png_bbox_and_old_job_cannot_publish_over_new(lab):
    first=create(lab)
    late=lab.store.claim()
    second=edit(lab,first,content(messages=[dict(id='m1',text='新版文字 '*30)]))
    newer=lab.store.claim()
    assert newer['id']==second['job_id']
    await lab.worker.execute(newer)
    await lab.worker.execute(late)
    s=lab.review.sample('alice',first['sample']['id'])
    m=lab.store.get('review.manifest',s['published_manifest'],'alice')
    assert m['revision']==2
    assert m['text_hash']==second['revision']['content_hash']
    assert m['pages'][0]['boxes'][0]['message_id']=='m1'
    assert verified(lab.store.root,m['pages'][0]).read_bytes().startswith(b'\x89PNG')

async def test_real_worker_process_crash_resumes_verified_pages_and_repairs_corruption(lab):
    text='长消息段落。'*500
    saved=create(lab,content(messages=[dict(id='m1',text=text)]))
    code="""
import asyncio,os,sys
from screenshotlegal.research.store import Store
from screenshotlegal.research.renderer import render_revision
from screenshotlegal.research.contracts import now
store=Store(sys.argv[1])
job=store.claim()
async def checkpoint(key,value,phase):
    with store.tx() as db:
        current=store.job(job['id'],job['owner'],db)
        current['checkpoints'][key]=value
        current['phase']=phase
        store.save_job(db,current,job['lease_token'])
    if key=='2':
        os._exit(73)
async def alive(): pass
asyncio.run(render_revision(store,job,checkpoint,alive))
"""
    crashed=subprocess.run([sys.executable,'-c',code,str(lab.store.root.parent)],capture_output=True)
    assert crashed.returncode==73,crashed.stderr.decode(errors='replace')
    old=lab.store.job(saved['job_id'],'alice')
    assert old['status']=='running' and len(old['checkpoints'])==2
    first=verified(lab.store.root,old['checkpoints']['1'])
    mtime=first.stat().st_mtime_ns
    second=verified(lab.store.root,old['checkpoints']['2'])
    second.write_bytes(b'corrupted half file')
    with lab.store.tx() as db:
        db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(old['id'],))
    restarted=Store(lab.store.root.parent)
    lab.worker.store=restarted
    resumed=restarted.claim()
    await lab.worker.execute(resumed)
    finished=restarted.job(old['id'],'alice')
    assert finished['status']=='completed'
    assert first.stat().st_mtime_ns==mtime
    assert verified(restarted.root,finished['checkpoints']['2']).read_bytes().startswith(b'\x89PNG')

async def test_release_needs_current_human_and_complete_render(lab):
    saved=create(lab); sid=saved['sample']['id']
    payload=ReleaseCreate(name='frozen',sample_ids=[sid],idempotency_key='release')
    with pytest.raises(Conflict):
        lab.review.create_release('alice',payload)
    await drain(lab)
    human(lab,sid)
    frozen=lab.review.create_release('alice',payload)
    edit(lab,saved)
    assert lab.review.release('alice',frozen['id'])['entries'][0]['revision']['number']==1
    with pytest.raises(Conflict):
        lab.review.create_release('alice',payload.model_copy(update={'idempotency_key':'other'}))

async def test_generation_demo_prompt_snapshot_and_quality_flow(lab):
    source=create(lab); p=prompt(lab)
    b=lab.studio.create_batch('alice',BatchCreate(name='batch',dataset='generated',source_sample_id=source['sample']['id'],source_revision=1,prompt_id=p['id'],count=2,idempotency_key='batch'))
    await drain(lab)
    row=lab.studio.batches('alice')[0]
    assert len(row['sample_ids'])==2
    candidate=lab.review.detail('alice',row['sample_ids'][0])
    assert not any(q['gold'] for q in candidate['revision']['content']['questions'])
    assert candidate['sample']['prompt_id']==p['id']
    assert candidate['sample']['published_manifest']
    qp=prompt(lab,'review')
    lab.review.queue_quality('alice',candidate['sample']['id'],QualityRun(revision=1,prompt_id=qp['id'],model_id='demo',idempotency_key='quality'),lab.gateway.freeze('alice','demo'))
    await drain(lab)
    qs=lab.review.detail('alice',candidate['sample']['id'])['quality']
    assert qs[0]['method']=='model' and qs[0]['score'] is None and qs[0]['prompt_id']==qp['id']
    assert lab.store.job(b['job_id'],'alice')['checkpoints']['response:0']['demo']

async def test_invalid_model_generation_keeps_raw_response(lab,monkeypatch):
    source=create(lab); p=prompt(lab)
    async def fake(*args):
        return dict(raw='invalid JSON',latency_ms=1,usage=None,demo=False)
    monkeypatch.setattr(lab.gateway,'call',fake)
    b=lab.studio.create_batch('alice',BatchCreate(name='bad',dataset='g',source_sample_id=source['sample']['id'],source_revision=1,prompt_id=p['id'],idempotency_key='bad'))
    await drain(lab)
    job=lab.store.job(b['job_id'],'alice')
    assert job['status']=='failed' and job['error']['category']=='response_parse'
    assert job['checkpoints']['response:0']['raw']=='invalid JSON'

async def test_evaluation_whitelist_and_frozen_inputs(lab,monkeypatch):
    saved,r=await release(lab,gold=True)
    payload=EvaluationCreate(name='run',release_id=r['id'],model_ids=['demo'],idempotency_key='eval')
    run=lab.evaluation.create_run('alice',payload)
    sent=[]
    async def fake(owner,model,messages,purpose,id):
        sent.append(messages)
        return dict(raw='GOLD_SENTINEL',usage={'prompt_tokens':10,'completion_tokens':2},latency_ms=12,demo=False)
    monkeypatch.setattr(lab.gateway,'call',fake)
    edit(lab,saved,content(messages=[dict(id='m1',text='修改后，不该进入旧运行')]))
    await drain(lab)
    text=json.dumps(sent,ensure_ascii=False)
    assert 'GOLD_SENTINEL' not in text and 'PRIVATE SOURCE' not in text and '修改后' not in text
    results=lab.evaluation.results('alice',run['id'])
    assert results['report']['models'][0]['scored']==1 and results['report']['models'][0]['unscored']==1
    assert results['report']['models'][0]['accuracy']==1
    assert results['run']['tasks'][0]['revision']==1
    assert lab.store.get('evaluation.metrics',run['id'],'alice')['models'][0]['scored']==1

async def test_image_modes_use_verified_bytes_and_fail_single_page_constraint(lab):
    saved,r=await release(lab)
    entry=r['entries'][0]; q=entry['revision']['content']['questions'][0]
    image=evaluation_input(entry,q,'image')
    assert 'messages' not in image and 'gold_answer' not in image
    messages=request_messages(lab.store,image)
    assert messages[1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    entry['manifest']['pages']*=2
    with pytest.raises(ModelFailure):
        evaluation_input(entry,q,'multimodal')
    assert len(evaluation_input(entry,q,'multi_image')['images'])==2
    asset=image['images'][0]
    verified(lab.store.root,asset).write_bytes(b'bad')
    with pytest.raises(ValueError):
        request_messages(lab.store,image)
    run=lab.evaluation.create_run('alice',EvaluationCreate(name='corrupt image',release_id=r['id'],model_ids=['demo'],mode='image',idempotency_key='corrupt'))
    await drain(lab)
    assert all(a['error']['category']=='source_file' for a in lab.evaluation.results('alice',run['id'])['attempts'])

async def test_failed_retry_preserves_exact_snapshots(lab,monkeypatch):
    _,r=await release(lab)
    run=lab.evaluation.create_run('alice',EvaluationCreate(name='run',release_id=r['id'],model_ids=['demo'],idempotency_key='eval'))
    async def failed(*args):
        raise ModelFailure('rate_limit','HTTP 429',True)
    monkeypatch.setattr(lab.gateway,'call',failed)
    await drain(lab)
    result=lab.evaluation.results('alice',run['id'])
    assert result['run']['status']=='failed' and len(result['attempts'])==2
    retry=lab.evaluation.retry('alice',run['id'],[run['tasks'][0]['id']],'retry')
    assert retry['parent_run_id']==run['id'] and len(retry['tasks'])==1
    assert retry['tasks'][0]['input_hash']==run['tasks'][0]['input_hash']
    assert retry['tasks'][0]['model']==run['tasks'][0]['model']
    assert retry['release_hash']==run['release_hash']

async def test_model_crash_is_unknown_and_not_automatically_replayed(lab):
    saved=create(lab); p=prompt(lab)
    b=lab.studio.create_batch('alice',BatchCreate(name='unknown',dataset='g',source_sample_id=saved['sample']['id'],source_revision=1,prompt_id=p['id'],idempotency_key='unknown'))
    await lab.worker.execute(lab.store.claim()) # source render
    job=lab.store.claim()
    with lab.store.tx() as db:
        job['phase']='calling_model'
        lab.store.save_job(db,job,job['lease_token'])
        db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(job['id'],))
    recovered=lab.store.claim()
    assert recovered['status']=='unknown'
    await lab.worker.execute(recovered)
    assert lab.store.job(b['job_id'],'alice')['status']=='unknown'
    assert not lab.studio.batches('alice')[0]['sample_ids']
    assert lab.store.claim() is None

def test_research_api_auth_isolation_and_original_asset_upload(accounts):
    w,admin,alice,bob=accounts
    payload=dict(dataset='private',content=content().model_dump(),note='create',idempotency_key='api')
    response=alice.post('/v1/review/samples',json=payload)
    assert response.status_code==201,response.text
    sid=response.json()['sample']['id']
    assert bob.get('/v1/review/samples/'+sid).status_code==404
    assert bob.get('/v1/review/samples').json()==[]
    assert admin.get('/v1/review/samples/'+sid).status_code==404
    assert alice.post('/v1/review/samples',json=payload).json()==response.json()
    import io
    image=io.BytesIO()
    from PIL import Image
    Image.new('RGB',(40,40),'white').save(image,format='PNG')
    a=alice.post('/v1/review/assets',files={'file':('original.png',image.getvalue(),'image/png')}).json()
    assert bob.get('/v1/review/assets/'+a['id']).status_code==404
    b=bob.post('/v1/review/assets',files={'file':('same.png',image.getvalue(),'image/png')}).json()
    assert a['id']==b['id'] and bob.get('/v1/review/assets/'+b['id']).status_code==200
    original=content(kind='original',original_assets=[a])
    created=alice.post('/v1/review/samples',json=dict(payload,content=original.model_dump(),idempotency_key='original')).json()
    bad=original.model_copy(update={'source_text':'overwrite original'})
    result=alice.put('/v1/review/samples/'+created['sample']['id'],json=dict(content=bad.model_dump(),expected_revision=1,note='overwrite',idempotency_key='bad'))
    assert result.status_code==409

def test_catalog_import_preserves_candidates_and_deduplicates(lab):
    catalog=Catalog(lab.store,lab.review)
    group=next(g for g in catalog.groups() if g['id']=='datasets/v2.0.0/round_001')
    assert group['count']>0
    first=catalog.import_group('alice',group['id'])
    assert first['imported']>0 and not first['failed'],first
    second=catalog.import_group('alice',group['id'])
    assert second['imported']==0 and second['duplicates']==first['imported']
    s=lab.review.detail('alice',first['sample_ids'][0])
    assert s['revision']['content']['source_refs'] and s['revision']['content']['original_assets']
    assert not any(q['gold'] for q in s['revision']['content']['questions'])

async def test_gateway_uses_frozen_endpoint_model_and_encrypted_credential(lab,workspace,monkeypatch):
    import httpx
    from pydantic import SecretStr
    from screenshotlegal.domain.settings.models import ModelConfiguration
    gateway=Gateway(lab.store,workspace)
    pref=workspace.preferences('alice')
    original=ModelConfiguration(name='original',base_url='https://frozen.test/v1',model_name='frozen-model',
                                api_key=SecretStr('frozen-private-key'),allow_external_egress=True,supports_vision=True)
    row=pref.save_model(original)
    snapshot=gateway.freeze('alice',row.id,vision=True)
    pref.save_model(original.model_copy(update={'model_name':'new-model','base_url':'https://changed.test/v1','api_key':SecretStr('changed-key')}),row.id)
    pref.delete_model(row.id)
    captured=[]
    def respond(request):
        captured.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':'answer'}}],'usage':{'prompt_tokens':10,'completion_tokens':3}})
    client=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:client(transport=httpx.MockTransport(respond),**kwargs))
    result=await gateway.call('alice',snapshot,[{'role':'user','content':'input'}],'evaluation','request')
    assert result['raw']=='answer' and result['usage']['prompt_tokens']==10
    assert str(captured[0].url)=='https://frozen.test/v1/chat/completions'
    assert captured[0].headers['authorization']=='Bearer frozen-private-key'
    assert json.loads(captured[0].content)['model']=='frozen-model'
    assert 'private-key' not in dumps(snapshot)
    credential=lab.store.get('gateway.credential',snapshot['credential_ref'],'alice')
    assert 'private-key' not in credential['ciphertext']
    with pytest.raises(KeyError):
        lab.store.get('gateway.credential',snapshot['credential_ref'],'bob')

@pytest.mark.parametrize('code,category,retryable',[(401,'auth',False),(429,'rate_limit',True),(413,'input_unsupported',False),(503,'network',True)])
async def test_gateway_classifies_errors_without_provider_body_or_key(lab,workspace,monkeypatch,code,category,retryable):
    import httpx
    from pydantic import SecretStr
    from screenshotlegal.domain.settings.models import ModelConfiguration
    gateway=Gateway(lab.store,workspace)
    row=workspace.preferences('alice').save_model(ModelConfiguration(name='test',base_url='https://unit.test/v1',model_name='model',api_key=SecretStr('private-test-key'),allow_external_egress=True))
    snapshot=gateway.freeze('alice',row.id)
    client=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:client(transport=httpx.MockTransport(lambda request:httpx.Response(code,text='private-test-key provider secret')),**kwargs))
    with pytest.raises(ModelFailure) as captured:
        await gateway.call('alice',snapshot,[],'evaluation','request')
    assert captured.value.category==category and captured.value.retryable==retryable
    assert 'private-test-key' not in str(captured.value) and 'provider secret' not in str(captured.value)

async def test_cancellation_keeps_queue_and_avoids_model_calls(lab,monkeypatch):
    _,r=await release(lab)
    run=lab.evaluation.create_run('alice',EvaluationCreate(name='cancel',release_id=r['id'],model_ids=['demo'],idempotency_key='cancel'))
    calls=[]
    async def unexpected(*args):
        calls.append(args)
    monkeypatch.setattr(lab.gateway,'call',unexpected)
    with lab.store.tx() as db:
        job=lab.store.job(run['job_id'],'alice',db)
        job['cancel_requested']=True
        lab.store.save_job(db,job)
    await drain(lab)
    result=lab.evaluation.results('alice',run['id'])
    assert result['run']['status']=='cancelled' and not calls
    assert all(a['status']=='cancelled' and a['score'] is None for a in result['attempts'])

async def test_content_correction_invalidates_gold_even_for_direct_api(lab):
    saved=create(lab,content(questions=[dict(id='q1',question='?',answer='old gold',gold=True)]))
    corrected=edit(lab,saved,content(messages=[dict(id='m1',text='new text')],questions=[dict(id='q1',question='?',answer='old gold',gold=True)]))
    assert corrected['revision']['content']['questions'][0]['gold'] is False

def test_after_commit_process_exit_preserves_revision_and_outbox(lab):
    saved=create(lab)
    script="""
import os,sys
from screenshotlegal.research.store import Store
from screenshotlegal.research.review import ReviewDesk
from screenshotlegal.research.contracts import SampleEdit,Content
s=Store(sys.argv[1]); review=ReviewDesk(s); sid=sys.argv[2]
old=review.revision('alice',sid,1)
review.edit('alice',sid,SampleEdit(content=Content.model_validate(dict(old['content'],title='crash committed')),expected_revision=1,note='before crash',idempotency_key='crash'))
os._exit(74)
"""
    result=subprocess.run([sys.executable,'-c',script,str(lab.store.root.parent),saved['sample']['id']],capture_output=True)
    assert result.returncode==74,result.stderr.decode(errors='replace')
    reopened=ReviewDesk(Store(lab.store.root.parent))
    detail=reopened.detail('alice',saved['sample']['id'])
    assert detail['sample']['revision']==2 and detail['sample']['title']=='crash committed'
    assert len(detail['jobs'])==2 and detail['revision']['note']=='before crash'

def test_v3_import_keeps_reviewer_only_metadata_out_of_public_questions(lab):
    catalog=Catalog(lab.store,lab.review)
    group=next(g for g in catalog.groups() if g['id']=='datasets/v3.0.0/calibration_20261023_003')
    result=catalog.import_group('alice',group['id'])
    assert result['imported']==group['count'] and not result['failed'],result
    detail=lab.review.detail('alice',result['sample_ids'][0])
    assert detail['revision']['content']['metadata']['legacy_questions']
    assert all(q['answer'] is None and not q['gold'] for q in detail['revision']['content']['questions'])

async def test_model_quality_cannot_supersede_human_records(lab,monkeypatch):
    saved=create(lab); sid=saved['sample']['id']
    h=human(lab,sid)
    p=prompt(lab,'review')
    async def fake(*args):
        return dict(raw=dumps(dict(verdict='reject',score=10,supersedes=h['id'],findings='model',suggestions='check',process='model process')),usage=None,latency_ms=1,demo=False)
    monkeypatch.setattr(lab.gateway,'call',fake)
    lab.review.queue_quality('alice',sid,QualityRun(revision=1,prompt_id=p['id'],model_id='demo',idempotency_key='q'),lab.gateway.freeze('alice','demo'))
    await drain(lab)
    rows=lab.review.active_quality('alice')
    assert any(q['id']==h['id'] for q in rows)
    assert next(q for q in rows if q['method']=='model')['supersedes'] is None

def test_idempotent_evaluation_reuses_snapshot_without_resolving_changed_model(lab,monkeypatch):
    # A duplicate submission returns its committed result even if model config is no longer available.
    async def prepare():
        return await release(lab)
    _,r=asyncio.run(prepare())
    payload=EvaluationCreate(name='same',release_id=r['id'],model_ids=['demo'],idempotency_key='same')
    run=lab.evaluation.create_run('alice',payload)
    def deleted(*args,**kwargs):
        raise KeyError('deleted config')
    monkeypatch.setattr(lab.gateway,'freeze',deleted)
    assert lab.evaluation.create_run('alice',payload)==run

async def test_interrupted_inflight_evaluation_is_unknown_even_when_run_was_cancelled(lab):
    _,r=await release(lab)
    run=lab.evaluation.create_run('alice',EvaluationCreate(name='cancel inflight',release_id=r['id'],model_ids=['demo'],idempotency_key='cancel-inflight'))
    job=lab.store.claim()
    with lab.store.tx() as db:
        lab.store.put('evaluation.attempt',dict(id='inflight',run_id=run['id'],task_id=run['tasks'][0]['id'],status='calling_model',created_at=now(),score=None,scoring_status='unscored'), 'alice',db)
    lab.worker.finish(job,'cancelled')
    result=lab.evaluation.results('alice',run['id'])
    inflight=next(a for a in result['attempts'] if a['id']=='inflight')
    assert inflight['status']=='unknown' and inflight['error']['category']=='unknown_outcome'
    assert result['run']['status']=='cancelled'
    assert any(a['status']=='cancelled' for a in result['attempts'] if a['id']!='inflight')
