import copy
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from screenshotlegal.research.store import Store, Conflict
from screenshotlegal.research.contracts import digest
from screenshotlegal.research.screenshot_review import (
    ScreenshotReview, MessageReview, SaveMessage, SaveItem, ItemReview,
    LockRequest, RestoreRequest, project, at, VERSION,
)

@pytest.fixture
def panel(tmp_path):
    store=Store(tmp_path)
    yield ScreenshotReview(store)
    store.close()

def item(dataset='A', encoded=False):
    raw=dict(dialog_name='dialog', custom={'preserve':[1,2]}, conversation=[
        dict(speaker='甲',content='旧文字',timestamp=None,message_bbox={'min_x':1,'min_y':2,'max_x':100,'max_y':80},
             image={'url':'photo','caption':'保留'},transfer=[{'amount':20,'currency':'CNY'}],file={'name':'附件','extra':42},unknown_field={'nested':[1,None]}),
        dict(speaker='乙',content='多余消息',timestamp='10:00',message_bbox={'min_x':1,'min_y':90,'max_x':100,'max_y':160},image='',transfer=[],file=[]),
    ])
    outer={'id':'source','source_url':'https://source.invalid','structured_info':json.dumps(raw,ensure_ascii=False)} if encoded else raw
    keys=['structured_info','conversation'] if encoded else ['conversation']
    return dict(id=dataset.lower()+'001',dataset=dataset,original_json=outer,message_path=keys,messages=project(outer,keys),
                speakers=['甲','乙'],source_ref='source.json#/0',source_sha256=digest(outer),annotation_level='unverified' if dataset=='A' else 'synthetic',
                judgment_excerpt='双方通过微信协商还款。',asset={'sha256':'abc','path':'originals/abc.png','width':200,'height':300,'mime_type':'image/png'})

def setup(panel,d='A',encoded=False):
    panel.initialize('alice',d,[item(d,encoded)],{'source':'fixture'},0)

def save(panel,mid='m1',d='A',**kw):
    row=MessageReview(message_id=mid,verdict='correct',**kw) if 'verdict' not in kw else MessageReview(message_id=mid,**kw)
    return panel.save_message('alice',d,d.lower()+'001',mid,SaveMessage(expected_version=panel.state('alice',d)['version'],review=row))

def whole(panel,d='A',**kw):
    return panel.save_item('alice',d,d.lower()+'001',SaveItem(expected_version=panel.state('alice',d)['version'],review=ItemReview(**kw)))

def sign(backup):
    backup['export_sha256']=digest({k:v for k,v in backup.items() if k not in ['export_sha256','exported_at']})
    return backup

@pytest.mark.parametrize('encoded',[False,True])
def test_lossless_correction_extra_and_positioned_additions(panel,encoded):
    setup(panel,encoded=encoded)
    original=copy.deepcopy(panel.state('alice','A')['items'][0]['original_json'])
    save(panel,verdict='wrong_text',corrected_text='改后文字',note='核对原图，修正转录',field_patch={'image':{'caption':'新图注'}})
    save(panel,'m2',verdict='extra',note='截图中没有这条')
    whole(panel,verdict='needs_fix',comment='补一条',added_messages=[dict(id='added1',after_message_id='m1',speaker='甲',text='漏字',fields={'transfer':[{'amount':30}]})])
    backup=panel.export('alice','A')
    result=backup['items'][0]
    assert result['original_json']==original
    corrected=at(result['corrected_json'],result['message_path'])
    assert len(corrected)==2
    assert corrected[0]['content']=='改后文字'
    assert corrected[0]['message_bbox']==at(original,result['message_path'])[0]['message_bbox']
    assert corrected[0]['image']=={'url':'photo','caption':'新图注'}
    for field in ['transfer','file','unknown_field']:
        assert corrected[0][field]==at(original,result['message_path'])[0][field]
    assert corrected[1]['added'] and corrected[1]['transfer'][0]['amount']==30
    assert panel.state('alice','A')['items'][0]['original_json']==original
    if encoded:
        assert isinstance(result['original_json']['structured_info'],str)
        assert isinstance(result['corrected_json']['structured_info'],str)

def test_export_before_lock_roundtrip_and_failure_atomicity(panel):
    setup(panel)
    save(panel)
    backup=panel.export('alice','A')
    save(panel,'m2',verdict='extra',note='需删除')
    before=panel.state('alice','A')
    bad=copy.deepcopy(backup)
    bad['items'][0]['reviews'].append(dict(bad['items'][0]['reviews'][0],message_id='missing'))
    sign(bad)
    with pytest.raises(ValueError):
        panel.restore('alice','A',RestoreRequest(expected_version=before['version'],backup=bad))
    assert panel.state('alice','A')==before
    restored=panel.restore('alice','A',RestoreRequest(expected_version=before['version'],backup=backup))
    assert restored['counts']['messages_reviewed']==1
    assert restored['counts']['items_reviewed']==0
    assert restored['locked_at'] is None
    out=panel.export('alice','A')
    assert out['items']==backup['items']

def test_lock_requires_every_message_and_current_export_and_isolated_dataset(panel):
    setup(panel);setup(panel,'B')
    whole(panel,verdict='unreadable',comment='整图模糊')
    b=panel.export('alice','A')
    with pytest.raises(ValueError):
        panel.lock('alice','A',LockRequest(expected_version=b['version'],export_sha256=b['export_sha256']))
    save(panel,verdict='uncertain',note='模糊无法读出')
    save(panel,'m2',verdict='uncertain',note='遮挡无法读出')
    whole(panel,verdict='unreadable',comment='无法辨认')
    with pytest.raises(Conflict):
        panel.lock('alice','A',LockRequest(expected_version=panel.state('alice','A')['version'],export_sha256=b['export_sha256']))
    b=panel.export('alice','A')
    panel.lock('alice','A',LockRequest(expected_version=b['version'],export_sha256=b['export_sha256']))
    with pytest.raises(Conflict):
        save(panel)
    with pytest.raises(Conflict):
        whole(panel,verdict='discard',comment='不能写')
    with pytest.raises(Conflict):
        panel.restore('alice','A',RestoreRequest(expected_version=panel.state('alice','A')['version'],backup=b))
    assert panel.export('alice','A')['locked_at']
    assert panel.state('alice','B')['locked_at'] is None
    save(panel,d='B',origin_type='synthetic_completion',time_basis='unknown',speaker_basis='simulated')

def test_validation_rejects_empty_notes_wrong_dataset_unknown_speaker_and_default_correct(panel):
    setup(panel)
    for kwargs in [
        dict(verdict='wrong_text',corrected_text='新文字'),
        dict(verdict='wrong_speaker',corrected_speaker='陌生人',note='改'),
        dict(verdict='correct',field_patch={'file':[]}),
        dict(verdict='wrong_time',corrected_time='10:01',note='改',corrected_text='不应该'),
    ]:
        with pytest.raises(ValueError):save(panel,**kwargs)
    with pytest.raises(ValueError):whole(panel,verdict='regen',comment='x',regen_instruction='x')
    with pytest.raises(ValueError):whole(panel,verdict='pass')
    assert panel.state('alice','A')['message_reviews']=={}

def test_b_facts_quote_time_and_regen_extra_exclusion(panel):
    setup(panel,'B')
    with pytest.raises(ValueError):save(panel,d='B')
    with pytest.raises(ValueError):save(panel,d='B',origin_type='verbatim_quote',source_quote='不在原文',time_basis='unknown',speaker_basis='simulated')
    with pytest.raises(ValueError):save(panel,'m2',d='B',origin_type='synthetic_completion',source_quote='双方通过微信协商还款。',time_basis='source',speaker_basis='simulated')
    save(panel,d='B',verdict='wrong_text',corrected_text='商量一下还款吧',note='明确是模拟措辞',origin_type='synthetic_completion',time_basis='unknown',speaker_basis='simulated')
    save(panel,'m2',d='B',verdict='extra',note='删除无依据的时间',origin_type='unsupported',time_basis='simulated',speaker_basis='simulated')
    with pytest.raises(ValueError):whole(panel,d='B',verdict='regen',comment='删除错话')
    whole(panel,d='B',verdict='regen',comment='删除错话',regen_instruction='仅按修正目标生成，明确合成性质')
    result=panel.regen('alice')
    job=result['jobs'][0]
    assert result['synthetic'] and job['synthetic']
    assert job['must_delete_message_ids']==['m2']
    assert [m['id'] for m in job['corrected_dialogue']]==['m1']
    assert job['corrected_dialogue'][0]['content']=='商量一下还款吧'
    assert '不是真实聊天记录' in result['fact_policy']

def test_edit_invalidates_whole_verdict_and_compare_and_swap(panel):
    setup(panel)
    save(panel);save(panel,'m2');whole(panel,verdict='pass')
    save(panel,'m1')
    assert panel.state('alice','A')['item_reviews']=={}
    version=panel.state('alice','A')['version']
    def attempt(note):
        try:
            panel.save_message('alice','A','a001','m1',SaveMessage(expected_version=version,review=MessageReview(message_id='m1',verdict='correct',note=note)))
            return 'ok'
        except Conflict:return 'conflict'
    with ThreadPoolExecutor(2) as ex:
        assert sorted(ex.map(attempt,['a','b']))==['conflict','ok']

def test_scope_owner_and_restore_checksum_boundaries(panel):
    setup(panel)
    backup=panel.export('alice','A')
    assert not panel.state('bob','A')['items']
    with pytest.raises(ValueError):
        panel.restore('bob','A',RestoreRequest(expected_version=0,backup=backup))
    backup['items'][0]['original_json']['custom']='tamper'
    sign(backup)
    before=panel.state('alice','A')
    with pytest.raises(ValueError):
        panel.restore('alice','A',RestoreRequest(expected_version=before['version'],backup=backup))
    assert panel.state('alice','A')==before

def test_multimodal_only_correction_and_bbox_validation(panel):
    setup(panel)
    save(panel,verdict='wrong_fields',note='图片字段修正，文字不变',field_patch={'image':{'caption':'清晰可见'},'transfer':[{'amount':30}]})
    row=panel.export('alice','A')['items'][0]
    assert row['corrected_messages'][0]['content']=='旧文字'
    assert row['corrected_messages'][0]['image']=={'url':'photo','caption':'清晰可见'}
    with pytest.raises(ValueError):
        save(panel,verdict='wrong_fields',note='无效框',field_patch={'message_bbox':{'min_x':120,'max_x':100}})

def test_recovery_rejects_all_bad_rows_without_partial_writes(panel):
    setup(panel)
    save(panel);save(panel,'m2')
    whole(panel,verdict='pass')
    backup=panel.export('alice','A')
    bad=copy.deepcopy(backup)
    bad['items'][0]['reviews'][0]['verdict']='wrong_text'
    bad['items'][0]['reviews'][0]['corrected_text']='changed'
    bad['items'][0]['reviews'][0]['note']='valid first row'
    bad['items'][0]['reviews'][1]['verdict']='wrong_speaker'
    bad['items'][0]['reviews'][1]['corrected_speaker']='outside roster'
    bad['items'][0]['reviews'][1]['note']='invalid second row'
    sign(bad)
    before=panel.state('alice','A')
    with pytest.raises(ValueError):
        panel.restore('alice','A',RestoreRequest(expected_version=before['version'],backup=bad))
    assert panel.state('alice','A')==before


@pytest.mark.parametrize('field,value',[
    ('message_mapping',[{'id':'m1','source_index':1}]),
    ('message_path',['not_the_original_list']),
    ('source_ref','different-source.json'),
    ('synthetic',True),
    ('reviews',None),
])
def test_restore_rejects_recomputed_checksum_with_altered_mapping(panel,field,value):
    setup(panel,encoded=True)
    backup=panel.export('alice','A')
    backup['items'][0][field]=value
    sign(backup)
    before=panel.state('alice','A')
    with pytest.raises(ValueError):
        panel.restore('alice','A',RestoreRequest(expected_version=before['version'],backup=backup))
    assert panel.state('alice','A')==before
