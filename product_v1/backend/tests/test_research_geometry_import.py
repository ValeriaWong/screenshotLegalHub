import json
from pathlib import Path
from test_research_products import lab,drain
from screenshotlegal.research.catalog import Catalog

async def test_v2_historical_xywh_boxes_stay_on_original_pixels(lab,monkeypatch):
    from screenshotlegal.research import catalog
    root=Path(__file__).resolve().parents[3]
    groups=Catalog(lab.store,lab.review).groups()
    group=next(g for g in groups if g['id']=='datasets/v2.0.0/round_006')
    file=next((root/group['id']).glob('*/*/case.json'))
    adapter=Catalog(lab.store,lab.review)
    monkeypatch.setattr(adapter,'candidates',lambda directory:[file])
    result=adapter.import_group('alice',group['id'])
    assert result['imported']==1 and result['failed']==[]
    await drain(lab)
    detail=lab.review.detail('alice',result['sample_ids'][0])
    m=lab.store.get('review.manifest',detail['sample']['published_manifest'],'alice')
    assert m['visual_role']=='original'
    assert m['pages'][0]['sha256']==detail['revision']['content']['original_assets'][0]['sha256']
    raw=json.loads((file.parent/'render.json').read_text(encoding='utf-8-sig'))['images'][0]['boxes'][0]
    x,y,w,h=raw['bbox_pixels']
    assert m['pages'][0]['boxes'][0]['bbox']==[x,y,x+w,y+h]
    assert adapter.import_group('alice',group['id'])['duplicates']==1


async def test_restore_original_adds_revision_keeps_id_and_refuses_changed_transcript(lab,monkeypatch):
    from screenshotlegal.research.contracts import Content,SampleCreate,SampleEdit,uid
    import pytest
    root=Path(__file__).resolve().parents[3]
    file=next((root/'datasets/v2.0.0/round_006').glob('*/*/case.json'))
    adapter=Catalog(lab.store,lab.review);monkeypatch.setattr(adapter,'candidates',lambda directory:[file])
    imported=adapter.import_group('alice','datasets/v2.0.0/round_006');await drain(lab)
    source=lab.review.detail('alice',imported['sample_ids'][0])['revision']['content']
    source=dict(source,visual_role='synthetic_render',original_layout=[])
    old=lab.review.create('alice',SampleCreate(dataset='legacy',content=Content.model_validate(source),note='legacy fixture',idempotency_key=uid('key')))
    sid=old['sample']['id'];await drain(lab)
    before=lab.review.revision('alice',sid,1)
    restored=adapter.restore_original('alice',sid,1,'restore')
    assert restored['sample']['id']==sid and restored['sample']['revision']==2
    assert adapter.restore_original('alice',sid,1,'restore')==restored
    await drain(lab)
    detail=lab.review.detail('alice',sid)
    m=lab.store.get('review.manifest',detail['sample']['published_manifest'],'alice')
    assert m['visual_role']=='original' and m['pages'][0]['sha256']==source['original_assets'][0]['sha256']
    assert lab.review.revision('alice',sid,1)==before
    changed=dict(detail['revision']['content']);changed['messages']=[dict(m,text=m['text']+' edited') for m in changed['messages']]
    lab.review.edit('alice',sid,SampleEdit(content=Content.model_validate(changed),expected_revision=2,note='human correction',idempotency_key='edit'))
    with pytest.raises(ValueError,match='消息已修改'):adapter.restore_original('alice',sid,3,'reject')
    assert lab.review.sample('alice',sid)['revision']==3
