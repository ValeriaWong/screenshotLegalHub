import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from screenshotlegal.domain.common.models import CaseCreate
from screenshotlegal.settings import ROOT


@pytest.fixture
def regions():
    spec=importlib.util.spec_from_file_location('region_sync',ROOT/'tools/sync_evidence_regions.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')


@pytest.fixture
def dataset(tmp_path,workspace):
    root=tmp_path/'repo';directory=root/'datasets/v2.0.0/round_003/zh/example/render.versions/old'
    directory.mkdir(parents=True)
    image=(ROOT/'fixtures/demo_private_lending/chat-1.png').read_bytes()
    (directory/'page.png').write_bytes(image)
    case=workspace.create_case(CaseCreate(title='Manual title',description='Manual description'),owner_id='admin')
    evidence=workspace.upload(case.id,'page.png','image/png',image)
    manifest=dict(images=[dict(path='page.png',sha256=hashlib.sha256(image).hexdigest(),boxes=[dict(message_id='unresolved-author-message',bbox_pixels=[10,20,100,40])])])
    save(directory/'render.json',manifest)
    report=root/'import.json';save(report,dict(results=[dict(aliases=[(directory/'render.json').relative_to(root).as_posix()])]))
    return root,directory,report,case,evidence


def test_orphan_geometry_creates_refs_without_inventing_messages_and_repeat_is_idempotent(regions,workspace,dataset,tmp_path):
    root,directory,report,case,evidence=dataset
    before={t:workspace.repo.list(t) for t in ['cases','messages','events','review_decisions','active_perceptions']}
    planned=regions.run(root,workspace,report,None,tmp_path/'plan',False)
    assert planned['new_region_refs']==1 and not workspace.repo.list('source_refs')
    first=regions.run(root,workspace,report,None,tmp_path/'first',True)
    assert first['model_calls']==0
    ref=workspace.repo.list('source_refs',case_id=case.id)[0]
    assert ref['bbox']==[10,20,110,60]
    assert ref['message_id'] is None and ref['quote']=='' and ref['evidence_page'] is None
    assert Path(first['backup']).is_file()
    assert {t:workspace.repo.list(t) for t in before}==before
    second=regions.run(root,workspace,report,None,tmp_path/'second',True)
    assert second['new_region_refs']==0 and len(workspace.repo.list('source_refs'))==1
    assert (tmp_path/'first/regions.reviewer_only.jsonl').read_bytes()==(tmp_path/'second/regions.reviewer_only.jsonl').read_bytes()


def test_only_byte_identical_images_can_share_geometry(regions,workspace,dataset):
    root,directory,report,case,evidence=dataset
    value=json.loads((directory/'render.json').read_text())
    value['images'][0]['sha256']='0'*64;save(directory/'render.json',value)
    with pytest.raises(ValueError,match='hash differs'): regions.collect(root,report,None)
    assert not workspace.repo.list('source_refs')


def test_outside_bounds_is_reported_not_clamped(regions,workspace,dataset,tmp_path):
    root,directory,report,case,evidence=dataset
    value=json.loads((directory/'render.json').read_text());value['images'][0]['boxes'][0]['bbox_pixels']=[-5,20,100,40]
    save(directory/'render.json',value)
    result=regions.run(root,workspace,report,None,tmp_path/'out',True)
    assert len(result['invalid_annotations'])==1 and result['new_region_refs']==0
    assert len(result['unlocated_images'])==1 and not workspace.repo.list('source_refs')


def test_labelu_elements_keep_geometry_but_never_import_semantic_attributes(regions,workspace,dataset,tmp_path):
    root,directory,report,case,evidence=dataset
    image_dir=root/'projects/quiz-collector/images';image_dir.mkdir(parents=True)
    (image_dir/'old.jpg').write_bytes((directory/'page.png').read_bytes())
    annotations=root/'annotations.json'
    save(annotations,[dict(fileName='old.jpg',result=json.dumps(dict(width=evidence.width,height=evidence.height,rotate=0,
        annotations=[dict(toolName='rectTool',result=[dict(x=12,y=22,width=30,height=40,label='avator',attributes={'legal_analysis':['NOT A FACT']})])])) )])
    result=regions.run(root,workspace,report,annotations,tmp_path/'out',True)
    assert result['new_region_refs']==2
    catalog=(tmp_path/'out/regions.reviewer_only.jsonl').read_text()
    assert 'annotated_element' in catalog and 'NOT A FACT' not in catalog
    assert not workspace.repo.list('messages') and not workspace.repo.list('events')


def test_existing_message_source_is_not_replaced(regions,workspace,dataset,tmp_path):
    root,directory,report,case,evidence=dataset
    existing=dict(id='human-ref',evidence_id=evidence.id,image_id=evidence.id,message_id='human-message',evidence_page=7,
        bbox=[10,20,110,60],raw_bbox=[10,20,110,60],raw_coordinate_space='pixels',quote='human quote')
    workspace.repo.put('source_refs',case.id+':human-ref',existing,case_id=case.id,immutable=True)
    result=regions.run(root,workspace,report,None,tmp_path/'out',True)
    assert result['new_region_refs']==0
    assert workspace.repo.list('source_refs',case_id=case.id)==[existing]
