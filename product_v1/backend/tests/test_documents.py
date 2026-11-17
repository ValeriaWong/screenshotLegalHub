import json
import time
import pytest
from screenshotlegal.documents.service import Documents, normalized
from test_accounts_ingestion import accounts

class WindowAdapter:
    def __init__(self): self.calls=[]; self.fail=False
    def parse(self,source,start,count,cache):
        self.calls.append(start)
        if self.fail: raise ValueError('temporary failure')
        return dict(items=[dict(type='text',text='Page '+str(start+1),page_idx=start,bbox=[100,200,700,300])],
                    total_pages=7,complete=start+count>=7,producer='fixture')
def pdf_doc(service,case_id='case'):
    return service.ingest(case_id,'paper.pdf',b'%PDF-1.4\nfixture')

def test_checkpoints_survive_recreation_and_failed_next_window(workspace):
    adapter=WindowAdapter();service=Documents(workspace,adapter);doc=pdf_doc(service)
    first=service.parse_next('case',doc['id'],3)
    assert first['parsed_pages']==3 and first['status']=='partial'
    adapter.fail=True
    with pytest.raises(ValueError):service.parse_next('case',doc['id'],3)
    assert service.read('case',doc['id'])['items'][0]['page']==1
    adapter.fail=False
    restarted=Documents(workspace,adapter)
    second=restarted.parse_next('case',doc['id'],3)
    assert second['parsed_pages']==6
    final=restarted.parse_next('case',doc['id'],3)
    assert final['status']=='complete'
    assert adapter.calls==[0,3,3,6]
    assert [b['page'] for b in restarted.read('case',doc['id'])['items']]==[1,4,7]
    restarted.parse_next('case',doc['id'],3)
    assert adapter.calls==[0,3,3,6]

def test_leases_prevent_duplicate_parse_and_allow_expired_window_recovery(workspace):
    service=Documents(workspace,WindowAdapter());doc=pdf_doc(service)
    with service.store.tx() as db:
        row=service.store.get('case',doc['id'],db);row.update(lease='old',lease_until=time.time()+100,status='parsing');service.store.put(row,db)
    with pytest.raises(ValueError,match='正在解析'):service.parse_next('case',doc['id'])
    with service.store.tx() as db:
        row=service.store.get('case',doc['id'],db);row['lease_until']=0;service.store.put(row,db)
    assert service.parse_next('case',doc['id'])['blocks']==1

def test_original_identity_notes_conflicts_and_case_scope(workspace):
    service=Documents(workspace);doc=service.ingest('a','notes.txt','金额 520 元。\n'.encode())
    assert service.ingest('a','renamed.txt','金额 520 元。\n'.encode())['id']==doc['id']
    assert service.ingest('b','notes.txt','金额 520 元。\n'.encode())['id']!=doc['id']
    with pytest.raises(KeyError):service.read('b',doc['id'])
    service.parse_next('a',doc['id'])
    before=service.source(doc).read_bytes()
    assert service.store.save_note(doc['id'],'reading',0,'人工核对',0,'alice')['revision']==1
    with pytest.raises(ValueError,match='新版本'):service.store.save_note(doc['id'],'reading',0,'stale',0,'bob')
    assert service.store.note(doc['id'],'reading')['text']=='人工核对'
    assert service.source(doc).read_bytes()==before
    service.source(doc).write_bytes(b'tampered')
    with pytest.raises(ValueError,match='完整性'):service.source(doc)

def test_raw_units_and_missing_coordinates_are_explicit():
    rows=normalized([dict(type='text',page_idx=8,bbox=[100,200,300,400],text='Original'),
                     dict(type='text',page_idx=8,bbox=[0,0,2000,300],text='No box')],'doc',12)
    assert rows[0]['page']==9 and rows[0]['bbox']==[100,200,300,400]
    assert rows[0]['locator']=='document:doc/page:9/block:12'
    assert rows[1]['bbox'] is None and rows[1]['coordinate_space'] is None

def test_documents_api_permission_validation_and_note_conflict(accounts):
    w,admin,alice,bob=accounts
    case=alice.post('/v1/cases',json=dict(title='Documents')).json()['id']
    root='/v1/cases/'+case+'/documents'
    uploaded=alice.post(root,files={'file':('notes.txt','真实原文 金额 520 元。'.encode(),'text/plain')})
    assert uploaded.status_code==201
    doc=uploaded.json();id=doc['id']
    assert bob.get(root).status_code==404
    assert alice.post(root+'/'+id+'/parse-next',json=dict(pages=3)).status_code==200
    detail=alice.get(root+'/'+id).json()
    assert '金额 520' in detail['items'][0]['text']
    note=dict(expected_revision=0,text='人工核对',cursor=0)
    assert alice.put(root+'/'+id+'/note',json=note).status_code==200
    assert alice.put(root+'/'+id+'/note',json=note).status_code==409
    assert alice.get(root+'/'+id+'/file').content=='真实原文 金额 520 元。'.encode()
    assert alice.post(root,files={'file':('fake.pdf',b'wrong','application/pdf')}).status_code==409
    alice.put('/v1/cases/'+case+'/members',json=dict(username='bob',role='viewer'))
    assert bob.get(root+'/'+id).status_code==200
    assert bob.post(root+'/'+id+'/parse-next',json=dict(pages=3)).status_code==403
    assert bob.put(root+'/'+id+'/note',json=note).status_code==403

@pytest.mark.asyncio
async def test_analysis_cannot_cite_other_blocks_and_does_not_auto_retry(workspace,monkeypatch):
    from types import SimpleNamespace
    from screenshotlegal.infrastructure.model.providers import OpenAICompatibleProvider
    service=Documents(workspace);doc=service.ingest('a','notes.txt',b'Visible source');service.parse_next('a',doc['id'])
    monkeypatch.setattr(workspace,'preferences',lambda _:SimpleNamespace(provider_settings=lambda _:SimpleNamespace(model_name='fixture')))
    calls=[]
    async def complete(self,*args):
        calls.append(args)
        return json.dumps(dict(summary='analysis',citations=['document:OTHER/page:1/block:0']))
    monkeypatch.setattr(OpenAICompatibleProvider,'complete',complete)
    with pytest.raises(ValueError,match='范围外'):await service.analyze(SimpleNamespace(id='alice'),'a',doc['id'],0,5,'m','analyze')
    assert len(calls)==1
    saved=service.store.analyses(doc['id'])[0]
    assert saved['status']=='unknown' and saved['result'] is None
    assert 'model_name' in saved and 'api_key' not in json.dumps(saved)
    async def grounded(self,*args):
        return json.dumps(dict(summary='analysis',citations=[service.read('a',doc['id'])['items'][0]['locator']],uncertainties=['需要人工核对']))
    monkeypatch.setattr(OpenAICompatibleProvider,'complete',grounded)
    assert (await service.analyze(SimpleNamespace(id='alice'),'a',doc['id'],0,5,'m','analyze'))['status']=='complete'

def test_table_cells_are_safe_text_and_block_reads_are_bounded(workspace):
    rows=normalized([dict(type="table",page_idx=0,table_body="<table><tr><th>Amount</th></tr><tr><td>520</td></tr></table>")],"d",0)
    assert rows[0]["table_rows"]==[["Amount"],["520"]]
    assert rows[0]["text"]=="Amount\n520"
    service=Documents(workspace);doc=service.ingest("a","long.txt",("x"*1600+"needle"+"y"*2000).encode())
    service.parse_next("a",doc["id"])
    result=service.read("a",doc["id"],0,1)
    assert len(result["items"])==1 and result["next_offset"]==1
    found=service.read("a",doc["id"],0,1,"needle")
    assert found["total"]==1 and found["items"][0]["ordinal"]==1

def test_presentation_bullets_keep_their_text_and_source_location():
    rows=normalized([dict(type="list",page_idx=2,list_items=["- Measured amount: 520 CNY"])],"slide",4)
    assert "520" in rows[0]["text"]
    assert rows[0]["page"]==3 and rows[0]["locator"]=="document:slide/page:3/block:4"
