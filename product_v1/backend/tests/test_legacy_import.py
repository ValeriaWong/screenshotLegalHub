import copy
import hashlib
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import text
from screenshotlegal.settings import ROOT
from screenshotlegal.domain.common.models import CaseCreate
from screenshotlegal.infrastructure.db.models import MODELS

spec = importlib.util.spec_from_file_location('legacy_import_under_test', ROOT/'tools/import_legacy_case.py')
legacy = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)

@pytest.fixture
def corpus():
    folder = ROOT/'fixtures/demo_private_lending'
    images = [dict(image_id=f'i{n}',file=f'chat-{n}.png',sha256=hashlib.sha256((folder/f'chat-{n}.png').read_bytes()).hexdigest()) for n in (1,2)]
    refs = [dict(image_id=f'i{n}',message_id=f'm{n}',bbox=[30,130,690,220],evidence_page=n,quote='borrow') for n in (1,2)]
    records = [dict(id=f'm{n}',kind='message',text='borrow',source_refs=[refs[n-1]]) for n in (1,2)]
    records.append(dict(id='e1',kind='event',text='agreement',source_refs=[refs[1]]))
    return dict(images=images,records=records), folder

def snapshot(workspace):
    data = {table:workspace.repo.list(table) for table in MODELS}
    with workspace.repo.engine.connect() as conn:
        data['fts'] = [tuple(row) for row in conn.execute(text('SELECT * FROM search_index'))]
    data['files'] = sorted((p.relative_to(workspace.storage.root).as_posix(),p.read_bytes()) for p in workspace.storage.root.rglob('*') if p.is_file())
    return data

@pytest.mark.parametrize('damage',['second_hash','missing_hash','escape','bad_ref','bad_event','bad_bbox','duplicate_image','duplicate_record','bad_event_text'])
async def test_preflight_leaves_no_case_or_file(workspace,corpus,damage):
    value, folder = corpus
    if damage=='bad_event_text': value['records'][-1]['text']=None
    if damage=='second_hash': value['images'][1]['sha256']='0'*64
    if damage=='missing_hash': del value['images'][1]['sha256']
    if damage=='escape': value['images'][1]['file']='../demo_private_lending/../../profiles/cn_civil_default.yaml'
    if damage=='bad_ref': value['records'][1]['source_refs'][0]['image_id']='missing'
    if damage=='bad_event': value['records'][-1]['source_refs'][0]['message_id']='missing'
    if damage=='bad_bbox': value['records'][1]['source_refs'][0]['bbox']=[0,0,999999,100]
    if damage=='duplicate_image': value['images'][1]['image_id']='i1'
    if damage=='duplicate_record': value['records'][1]['id']='m1'
    before = snapshot(workspace)
    with pytest.raises((ValueError,FileNotFoundError)):
        await legacy.import_case(workspace,value,folder,'Invalid import')
    assert snapshot(workspace)==before

@pytest.mark.parametrize('failure',['second_file','after_database','after_index'])
async def test_late_failure_rolls_back_and_retry_succeeds(workspace,corpus,monkeypatch,failure):
    value, folder=corpus
    existing = workspace.create_case(CaseCreate(title='Existing case'))
    workspace.upload(existing.id,'existing.png','image/png',(folder/'chat-1.png').read_bytes())
    before=snapshot(workspace)
    if failure=='second_file':
        original=workspace.storage.save; calls=0
        def fail(*args,**kwargs):
            nonlocal calls
            calls+=1
            item=original(*args,**kwargs)
            if calls==2: raise OSError('Injected second-file failure')
            return item
        target=workspace.storage; method='save'
    elif failure=='after_database':
        original=workspace.repo.batch
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise OSError('Injected database failure')
        target=workspace.repo; method='batch'
    else:
        original=workspace.retriever.index
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise OSError('Injected index failure')
        target=workspace.retriever; method='index'
    monkeypatch.setattr(target,method,fail)
    with pytest.raises(OSError): await legacy.import_case(workspace,value,folder,'Failing import')
    assert snapshot(workspace)==before
    monkeypatch.setattr(target,method,original)
    case=await legacy.import_case(workspace,value,folder,'Retry')
    assert len(workspace.repo.list('cases'))==2
    assert len(workspace.active_messages(case.id))==2
    assert workspace.retriever.search(case.id,'borrow')
    assert all(workspace.storage.verified_path(e).is_file() for e in workspace.evidence(case.id))

async def test_duplicate_text_uses_exact_legacy_message(workspace,corpus):
    value,folder=corpus
    second=copy.deepcopy(value['records'][0]);second['id']='different-message'
    second['source_refs'][0].update(message_id=second['id'],bbox=[40,240,680,300])
    value['records'].insert(1,second)
    value['records'][-1]['source_refs']=[second['source_refs'][0]]
    case=await legacy.import_case(workspace,value,folder,'Repeated text')
    event=workspace.repo.list('events',case_id=case.id)[0]
    refs={r['id']:r for r in workspace.repo.list('source_refs',case_id=case.id)}
    assert refs[event['source_refs'][0]]['bbox']==[40,240,680,300]
    assert event['review_status']=='unreviewed'

async def test_all_message_locations_preserved(workspace,corpus):
    value,folder=corpus
    extra=copy.deepcopy(value['records'][1]['source_refs'][0]);extra['message_id']='m1'
    value['records'][0]['source_refs'].append(extra)
    value['records'][-1]['source_refs']=[extra]
    case=await legacy.import_case(workspace,value,folder,'Multiple locations')
    refs=workspace.repo.list('source_refs',case_id=case.id)
    assert len(refs)==3
    assert len(workspace.active_messages(case.id))==3
    event=workspace.repo.list('events',case_id=case.id)[0]
    selected=next(r for r in refs if r['id']==event['source_refs'][0])
    assert selected['evidence_page']==2

async def test_unknown_page_is_preserved(workspace,corpus):
    value,folder=corpus
    for row in value['records']:
        for ref in row['source_refs']:ref['evidence_page']=None
    case=await legacy.import_case(workspace,value,folder,'Unknown pages')
    assert all(r['evidence_page'] is None for r in workspace.repo.list('source_refs',case_id=case.id))

async def test_mixed_cases_rejected_before_writes(workspace,corpus):
    value,folder=corpus
    value['images'][0]['case_id']='case-a';value['images'][1]['case_id']='case-b'
    before=snapshot(workspace)
    with pytest.raises(ValueError,match='one legacy case'):
        await legacy.import_case(workspace,value,folder,'Mixed cases')
    assert snapshot(workspace)==before

async def test_legacy_extension_does_not_override_actual_image(workspace,corpus,tmp_path):
    value,folder=corpus
    copied=tmp_path/'old-images';copied.mkdir()
    for image in value['images']:
        (copied/image['file']).write_bytes((folder/image['file']).read_bytes())
    (copied/'incorrect-name.jpg').write_bytes((folder/'chat-2.png').read_bytes())
    value['images'][1]['file']='incorrect-name.jpg'
    case=await legacy.import_case(workspace,value,copied,'Historical extension mismatch')
    image=next(e for e in workspace.evidence(case.id) if e['filename']=='incorrect-name.jpg')
    assert image['mime_type']=='image/png' and image['storage_path'].endswith('.png')
    assert image['sha256']==value['images'][1]['sha256']
