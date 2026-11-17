import pytest
from types import SimpleNamespace
from test_research_products import lab, prompt, drain
from screenshotlegal.research.screenshot_review import VERSION
from screenshotlegal.research.screenshot_regeneration import create_regeneration

def payload():
    return SimpleNamespace(package=dict(contract=VERSION,batch='chat-screenshot-review-regen',synthetic=True,jobs=[
        dict(item_id='b001',synthetic=True,judgment_excerpt='双方通过微信协商还款。',source_ref='test',
             instruction='仅按已审核修正目标生成，时间未知。',review_constraints='保持合成标识',
             corrected_dialogue=[dict(id='m1',speaker='甲',content='商量一下还款吧',timestamp=None,transfer=[{'amount':200}],file={'name':'keep'})],
             must_delete_message_ids=['m2'])]),
        item_id='b001',name='包重生成',prompt_id='',model_id='demo',idempotency_key='regen-test')

async def test_regenerate_only_from_package_and_no_live_panel_feedback(lab,monkeypatch):
    p=payload();p.prompt_id=prompt(lab)['id']
    monkeypatch.setattr(lab.studio,'feedback',lambda *args: (_ for _ in ()).throw(AssertionError('must not read live feedback')))
    batch=create_regeneration(lab.studio,'alice',p)
    assert batch['source']['content']['messages'][0]['text']=='商量一下还款吧'
    assert not batch['review_feedback']
    assert batch['source']['content']['metadata']['regeneration_package']==p.package
    assert create_regeneration(lab.studio,'alice',p)['id']==batch['id']
    await drain(lab)
    saved=lab.store.get('studio.batch',batch['id'],'alice')
    assert len(saved['sample_ids'])==1
    content=lab.review.detail('alice',saved['sample_ids'][0])['revision']['content']
    assert content['kind']=='synthetic'
    assert content['metadata']['synthetic'] and content['metadata']['factual_review_required']
    assert content['messages'][0]['origin_type']=='synthetic_completion'
    assert 'm2' not in [m['id'] for m in content['messages']]

def test_regen_rejects_deleted_messages_in_corrected_dialogue(lab):
    p=payload();p.package['jobs'][0]['corrected_dialogue'][0]['id']='m2'
    with pytest.raises(ValueError,match='删除'):
        create_regeneration(lab.studio,'alice',p)
