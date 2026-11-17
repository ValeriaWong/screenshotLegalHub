import json
from pathlib import Path
from PIL import Image
import pytest
from screenshotlegal.research.store import Store
from screenshotlegal.research.review import ReviewDesk
from screenshotlegal.research.screenshot_review import ScreenshotReview
from screenshotlegal.research.screenshot_sources import ScreenshotSources, A_FILE
from screenshotlegal.research.contracts import digest

def test_source_preflight_reports_exclusions_and_commits_only_acknowledged_scope(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    file=root/A_FILE;file.parent.mkdir(parents=True)
    image=root/'assets/one.png';image.parent.mkdir()
    Image.new('RGB',(200,300),'white').save(image)
    manifest=root/'reports/restart/images_manifest.json';manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps([dict(name='one.png',path='assets/one.png',sha256=digest(image.read_bytes()))]))
    rows=[dict(image_url='/old/one.png',structured_info=json.dumps(dict(conversation=[dict(content='text',speaker='甲',file={'keep':True},message_bbox={'min_x':1,'max_x':2,'min_y':1,'max_y':2})]))),
          dict(image_url='/old/one.png',structured_info='{broken'),
          dict(image_url='/old/missing.png',structured_info='{}')]
    file.write_text(json.dumps(rows))
    original=file.read_bytes()
    store=Store(tmp_path/'data');review=ReviewDesk(store)
    sources=ScreenshotSources(store,review,root);panel=ScreenshotReview(store)
    items,scope=sources.prepare('alice','legacy-kie')
    assert scope['items']==1 and scope['messages']==1 and len(scope['excluded'])==2
    assert items[0]['annotation_level']=='unverified' and items[0]['id']=='a001'
    assert not panel.state('alice','A')['items']
    with pytest.raises(ValueError,match='异常清单'):
        sources.initialize('alice',panel,'legacy-kie',scope['fingerprint'],0,False)
    assert not panel.state('alice','A')['items']
    sources.initialize('alice',panel,'legacy-kie',scope['fingerprint'],0,True)
    assert panel.export('alice','A')['items'][0]['original_json']==rows[0]
    assert file.read_bytes()==original
    rows[0]['changed']=True;file.write_text(json.dumps(rows))
    with pytest.raises(ValueError,match='来源已变化'):
        sources.initialize('bob',panel,'legacy-kie',scope['fingerprint'],0,True)
    assert not panel.state('bob','A')['items']
    store.close()


def test_legacy_b_render_maps_file_messages_and_page_without_losing_other_messages(tmp_path):
    root=tmp_path/'repo'
    directory=root/'datasets/v2.0.0/round_001/zh/case1'
    directory.mkdir(parents=True)
    image=directory/'page.png'
    Image.new('RGB',(200,300),'white').save(image)
    case=dict(messages=[
        dict(id='m1',sender_id='u1',text='模拟一',timestamp=None,image={'keep':'image'}),
        dict(id='m2',sender_id='u2',text='模拟二',timestamp=None,file={'keep':'file'}),
    ],custom={'keep':'case'})
    source=dict(text='双方通过微信协商。',case_no='example',url='https://example.invalid')
    render=dict(images=[
        dict(file='page.png',evidence_page=1,sha256=digest(image.read_bytes()),messages=[dict(message_id='m1',bbox=[120,20,190,80])]),
        dict(file='page.png',evidence_page=2,sha256=digest(image.read_bytes()),messages=[dict(message_id='m2',bbox=[10,20,80,80])]),
    ])
    for filename,value in [('curated.json',case),('source.json',source),('render.json',render)]:
        (directory/filename).write_text(json.dumps(value),encoding='utf-8')
    store=Store(tmp_path/'data')
    sources=ScreenshotSources(store,ReviewDesk(store),root)
    items,scope=sources.prepare('alice','repo:datasets/v2.0.0/round_001')
    assert scope['items']==2 and scope['messages']==2 and not scope['excluded']
    assert scope['source_records']==1 and scope['generated_versions']==1 and scope['judgment_texts']==1
    by_page={i['source_ref'].split('#page=')[1]:i for i in items}
    assert by_page['1']['messages'][0]['id']=='m1'
    assert by_page['1']['messages'][0]['side']=='right'
    assert by_page['2']['messages'][0]['id']=='m2'
    assert by_page['2']['messages'][0]['source_index']==1
    assert by_page['2']['messages'][0]['side']=='left'
    for item in items:
        assert item['original_json']==dict(case=case,source=source,render=render)
        assert item['synthetic'] and item['annotation_level']=='synthetic'
    assert by_page['1']['judgment_ref']=='example'
    store.close()


def test_b_counts_distinguish_shared_judgment_versions_and_screenshot_pages(tmp_path):
    root=tmp_path/'repo'
    base=root/'datasets/v2.0.0/round_001/zh'
    for version in ['v1','v2']:
        directory=base/version
        directory.mkdir(parents=True)
        image=directory/'page.png'
        Image.new('RGB',(200,300),'white').save(image)
        (directory/'source.json').write_text(json.dumps(dict(text='同一份完整判决原文。')),encoding='utf-8')
        (directory/'curated.json').write_text(json.dumps(dict(messages=[dict(id='m1',sender_id='u1',text=version)])),encoding='utf-8')
        (directory/'render.json').write_text(json.dumps(dict(images=[dict(file='page.png',evidence_page=1,messages=[dict(message_id='m1',bbox=[10,20,80,80])])])),encoding='utf-8')
    store=Store(tmp_path/'data')
    sources=ScreenshotSources(store,ReviewDesk(store),root)
    _,scope=sources.prepare('alice','repo:datasets/v2.0.0/round_001')
    assert scope['source_records']==2
    assert scope['judgment_texts']==1
    assert scope['generated_versions']==2
    assert scope['items']==2
    assert scope['messages']==2
    assert scope['versions_without_source_text']==0
    assert scope['source_title']
    store.close()
