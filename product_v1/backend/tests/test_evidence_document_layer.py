import asyncio
import json
import pytest
from pydantic import ValidationError
from screenshotlegal.documents.service import Documents, normalized
from screenshotlegal.documents.contracts import ReadRange
from screenshotlegal.documents.reading import read_snapshot
from screenshotlegal.documents.store import DocumentStore
from screenshotlegal.domain.evidence.documents import CoordinateFrame
from screenshotlegal.application.services.source_resolution import ResolveRequest, resolve_source
from test_accounts_ingestion import accounts
from test_documents import WindowAdapter, pdf_doc

def test_coordinate_units_origin_rotation_and_invalid_rectangles():
    assert CoordinateFrame(units="points",origin="bottom_left",width=200,height=100).normalized([20,10,60,30]) == pytest.approx([.1,.7,.3,.9])
    assert CoordinateFrame(units="pixels",width=200,height=100,rotation=90).normalized([20,10,60,30]) == pytest.approx([.7,.1,.9,.3])
    with pytest.raises(ValueError):CoordinateFrame(units="pixels",width=200,height=100).normalized([0,0,300,30])
    with pytest.raises(ValidationError):CoordinateFrame(units="pixels",width=0,height=100)

def test_merged_table_cells_keep_grid_spans_without_executing_html():
    row=normalized([dict(type="table",page_idx=0,table_body='<table><tr><th rowspan="2">类别</th><th colspan="2">金额</th></tr><tr><td>520</td><td>580</td></tr></table>')],"d",0)[0]
    assert row["table_rows"]==[["类别","金额"],["520","580"]]
    assert [(c["row"],c["column"],c["row_span"],c["column_span"]) for c in row["table_cells"]]==[(0,0,2,1),(0,1,1,2),(1,1,1,1),(1,2,1,1)]

def test_cross_block_unicode_continuation_reads_every_codepoint_once(workspace):
    service=Documents(workspace)
    text="甲😀乙"*180+"末尾"
    doc=service.ingest("c","unicode.txt",text.encode(),{"text_chunk_chars":200})
    service.parse_next("c",doc["id"]);snapshot=service.store.freeze("c",doc["id"])
    request=ReadRange(block_id=snapshot["blocks"][0]["id"],max_chars=157,across_blocks=True)
    parts=[];ranges=[]
    while True:
        result=read_snapshot(snapshot,request);parts.append(result["text"]);ranges+=result["content_ranges"]
        assert len(result["text"])<=157 and result["char_unit"]=="unicode_code_point"
        if not result["next_request"]:break
        request=ReadRange(**result["next_request"])
    assert "".join(parts)==text
    for block in snapshot["blocks"]:
        rr=[r for r in ranges if r["block_id"]==block["id"]]
        assert rr[0]["start"]==0 and rr[-1]["end"]==len(block["text"])
        assert all(a["end"]==b["start"] for a,b in zip(rr,rr[1:]))
    assert read_snapshot(snapshot,ReadRange(block_id=snapshot["blocks"][0]["id"],max_chars=300))["text"]==snapshot["blocks"][0]["text"]

def test_durable_jobs_deduplicate_recover_expired_claim_and_cancel(workspace):
    service=Documents(workspace,WindowAdapter());doc=pdf_doc(service)
    first=service.store.submit_job("case",doc["id"],3,True,"alice")
    assert service.store.submit_job("case",doc["id"],3,True,"alice")["id"]==first["id"]
    restarted=DocumentStore(workspace.settings.data_dir)
    claimed=restarted.claim_job()
    assert claimed["id"]==first["id"] and restarted.claim_job() is None
    with restarted.tx() as db:db.execute("UPDATE parse_jobs SET lease_until=0 WHERE id=?",(first["id"],))
    recovered=restarted.claim_job()
    assert recovered["lease_token"]!=claimed["lease_token"]
    row=service.parse_next("case",doc["id"],3)
    assert not restarted.settle_job(claimed,"succeeded",row)
    assert restarted.continue_job(recovered,row)
    assert restarted.job("case",first["id"])["parsed_pages"]==3
    assert restarted.cancel_job("case",first["id"])["status"]=="cancelled"
    assert restarted.claim_job() is None
    with pytest.raises(KeyError):restarted.job("other",first["id"])

@pytest.mark.asyncio
async def test_worker_all_pages_checkpoints_and_cancelled_jobs_never_parse(workspace):
    adapter=WindowAdapter();service=Documents(workspace,adapter);doc=pdf_doc(service)
    cancelled=service.store.submit_job("case",doc["id"],3,False,"a")
    service.store.cancel_job("case",cancelled["id"])
    job=service.store.submit_job("case",doc["id"],3,True,"a")
    worker=asyncio.create_task(service.loop())
    try:
        for _ in range(100):
            if service.store.job("case",job["id"])["status"]=="succeeded":break
            await asyncio.sleep(.03)
        assert service.store.job("case",job["id"])["status"]=="succeeded"
        assert adapter.calls==[0,3,6]
    finally:
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):await worker

def test_complete_block_index_includes_long_middle_and_pagination(workspace):
    service=Documents(workspace)
    text="头"*3000+" exclusiveMiddleToken "+"尾"*3000
    doc=service.ingest("c","middle.txt",text.encode(),{"text_chunk_chars":8000})
    service.parse_next("c",doc["id"])
    assert len(service.store.blocks(doc["id"],q="exclusiveMiddleToken"))==1
    assert service.store.blocks(doc["id"],q="exclusiveMiddleToken",offset=1,limit=1)==[]

def test_publication_retry_old_snapshot_and_ambiguous_quote(accounts,monkeypatch):
    workspace,admin,alice,bob=accounts
    cid=alice.post("/v1/cases",json={"title":"Frozen provenance"}).json()["id"]
    root="/v1/cases/"+cid+"/documents"
    doc=alice.post(root,files={"file":("p.txt","甲😀金额520；金额520。".encode(),"text/plain")}).json()
    assert alice.post(root+"/"+doc["id"]+"/parse-next",json={"pages":3}).status_code==200
    service=Documents(workspace)
    snapshot=service.store.freeze(cid,doc["id"])
    original_batch=workspace.repo.batch
    def broken(*a,**k):raise RuntimeError("projection unavailable")
    monkeypatch.setattr(workspace.repo,"batch",broken)
    with pytest.raises(RuntimeError):service.publish(cid,doc["id"],"alice")
    assert service.store.publications(cid)[0]["status"]=="failed"
    monkeypatch.setattr(workspace.repo,"batch",original_batch)
    assert service.publish(cid,doc["id"],"alice")["status"]=="published"
    assert service.publish(cid,doc["id"],"alice")["id"]==snapshot["id"]
    ref=next(r for r in workspace.repo.list("source_refs",case_id=cid) if r.get("source_kind")=="document")
    ambiguous=resolve_source(workspace,service,cid,ResolveRequest(source_ref_id=ref["id"],quote="金额520"))
    assert ambiguous["text_match"]=="ambiguous" and len(ambiguous["matches"])==2
    exact=resolve_source(workspace,service,cid,ResolveRequest(source_ref_id=ref["id"],quote="金额520",start=2,end=7))
    assert exact["text_match"]=="exact"
    with pytest.raises(ValueError):resolve_source(workspace,service,cid,ResolveRequest(source_ref_id=ref["id"],quote="金额520",start=0,end=5))
    with pytest.raises(KeyError):resolve_source(workspace,service,"other",ResolveRequest(source_ref_id=ref["id"]))
    typed=alice.get(root+"/"+doc["id"]+"/evidence-document")
    assert typed.status_code==200,typed.text
    assert typed.json()["blocks"][0]["locator"]
    other=alice.post(root+"/"+doc["id"]+"/parse-runs",json={"text_chunk_chars":200}).json()
    assert other["id"]!=doc["id"]
    assert service.store.snapshot(cid,snapshot["id"])==snapshot
    service.parse_next(cid,other["id"]);service.publish(cid,other["id"],"alice")
    active=alice.get("/v1/cases/"+cid+"/source-search",params={"q":"金额"}).json()["items"]
    assert {r["document_id"] for r in active if r["kind"]=="document"}=={other["id"]}
    assert resolve_source(workspace,service,cid,ResolveRequest(source_ref_id=ref["id"]))["source"]["parse_snapshot_id"]==snapshot["id"]
    assert alice.get("/v1/cases/"+cid+"/source-search",params={"q":"金额","document_id":doc["id"]}).json()["items"]
    assert bob.post("/v1/cases/"+cid+"/resolve-source",json={"source_ref_id":ref["id"]}).status_code==404

def test_frozen_message_resolver_uses_frozen_text_not_mutable_transcript(workspace):
    from types import SimpleNamespace
    from screenshotlegal.domain.common.models import digest
    class Repo:
        def get(self,table,id):
            if table=="analysis_runs":
                return {"case_id":"c","input_snapshot":{"source_refs":[dict(id="s",source_kind="message",evidence_id="e",text="😀冻结原文",bbox=None)]}}
            return {"id":"e","sha256":"sha"}
    fake=SimpleNamespace(repo=Repo(),storage=SimpleNamespace(verified_path=lambda _:None))
    value=resolve_source(fake,None,"c",ResolveRequest(source_ref_id="s",analysis_run_id="r",quote="冻结"))
    assert value["text_match"]=="exact" and value["matches"][0]["start"]==1

def test_artifact_cache_checks_original_bytes_and_detects_tampering(tmp_path):
    from screenshotlegal.documents.adapter import MinerUAdapter
    source=tmp_path/"one.pdf";source.write_bytes(b"%PDF-fixture")
    adapter=MinerUAdapter();calls=[]
    def call(payload):
        calls.append(payload)
        return dict(items=[],total_pages=1,complete=True,producer="fixture",middle_json={"native":"retained"})
    adapter.call=call
    first=adapter.parse(source,0,3,tmp_path/"cache")
    assert len(calls)==1
    assert adapter.parse(source,0,3,tmp_path/"cache")==first and len(calls)==1
    artifact=tmp_path/"cache"/first["artifact_manifest"]["filename"]
    artifact.write_bytes(b'{"tampered":true}')
    with pytest.raises(ValueError,match="完整性"):adapter.parse(source,0,3,tmp_path/"cache")
    source.write_bytes(b"%PDF-other")
    changed=adapter.parse(source,0,3,tmp_path/"cache")
    assert changed["artifact_manifest"]["source_sha256"]!=first["artifact_manifest"]["source_sha256"]
    assert len(calls)==2

def test_document_fact_ledger_resolves_run_snapshot_without_dangling_assets(accounts):
    import time
    from screenshotlegal.application.services.proof import graph
    workspace,_,alice,_=accounts
    cid=alice.post("/v1/cases",json={"title":"Document-only graph"}).json()["id"]
    root="/v1/cases/"+cid+"/documents"
    doc=alice.post(root,files={"file":("fact.txt","甲确认金额520元。".encode(),"text/plain")}).json()
    alice.post(root+"/"+doc["id"]+"/parse-next",json={"pages":3})
    response=alice.post("/v1/cases/"+cid+"/analysis/runs",json={"document_ids":[doc["id"]]})
    assert response.status_code==200,response.text
    rid=response.json()["id"]
    for _ in range(100):
        run=workspace.repo.get("analysis_runs",rid)
        if run["status"] in {"COMPLETED","FAILED"}:break
        time.sleep(.03)
    assert run["status"]=="COMPLETED"
    value=graph(workspace.repo,cid,rid);ids={e.id for e in value.entities}
    assert all(edge["source"] in ids and edge["target"] in ids for edge in value.edges)
    refs={r["id"]:r for r in run["input_snapshot"]["source_refs"]}
    assert value.citation_bindings
    assert all(b["source_text_digest"]==refs[b["source_ref_id"]]["text_digest"] for b in value.citation_bindings)
    for binding in value.citation_bindings:
        resolved=alice.post("/v1/cases/"+cid+"/resolve-source",json={"source_ref_id":binding["source_ref_id"],"analysis_run_id":rid})
        assert resolved.status_code==200,resolved.text
        assert resolved.json()["source"]["parse_snapshot_id"]==binding["snapshot_id"]
    assert not workspace.active_messages(cid)

def test_publication_ack_interruption_is_replayed_idempotently(workspace,monkeypatch):
    from types import SimpleNamespace
    case=workspace.create_case(SimpleNamespace(title="Outbox crash",description="")).model_dump()
    service=Documents(workspace)
    doc=service.ingest(case["id"],"source.txt",b"immutable original");service.parse_next(case["id"],doc["id"])
    original=service.store.publication_state
    def interrupt_ack(value,status,error=None):
        if status=="published":raise RuntimeError("process interrupted after core commit")
        return original(value,status,error)
    monkeypatch.setattr(service.store,"publication_state",interrupt_ack)
    with pytest.raises(RuntimeError,match="interrupted"):service.publish(case["id"],doc["id"])
    pending=service.store.publications(case["id"],pending=True)
    assert len(pending)==1
    before=workspace.repo.list("source_refs",case_id=case["id"])
    restarted=Documents(workspace)
    assert restarted.project_publication(pending[0])["status"]=="published"
    assert workspace.repo.list("source_refs",case_id=case["id"])==before
    assert not restarted.store.publications(case["id"],pending=True)


def test_vendor_hierarchy_uses_local_block_ids_and_keeps_raw_references():
    rows=normalized([dict(type='section_header',text='Title',source_ref='#/texts/0',parent_id='#/body',children=['#/texts/1']),dict(type='text',text='Body',source_ref='#/texts/1',parent_id='#/texts/0')],'doc',0)
    assert rows[0]['parent_id'] is None and rows[0]['children']==['b1']
    assert rows[1]['parent_id']=='b0'
    assert rows[0]['raw']['parent_id']=='#/body'
