import pytest
from test_accounts_ingestion import accounts, upload_files

def test_case_edit_is_versioned_preserves_sources_and_rejects_stale_writes(accounts):
    w, admin, alice, bob = accounts
    case = alice.post("/v1/cases", json={"title": "Original", "description": "Immutable import provenance"}).json()
    path = f"/v1/cases/{case['id']}/workbench"
    before = alice.get(path).json()
    assert before["case"]["revision"] == 0
    payload = {"title": " Updated ", "summary": "Working summary", "notes": "Notes", "expected_revision": 0}
    saved = alice.put(path, json=payload)
    assert saved.status_code == 200
    body = saved.json()
    assert body["title"] == "Updated" and body["revision"] == 1 and body["updated_at"]
    assert body["description"] == case["description"] and body["owner_id"] == "alice"
    assert alice.get(path).json()["case"]["notes"] == "Notes"
    assert alice.put(path, json=dict(payload, notes="stale overwrite")).status_code == 409
    assert alice.get(path).json()["case"]["notes"] == "Notes"
    assert alice.put(path, json=dict(payload, title=" ", expected_revision=1)).status_code == 422

def test_workbench_enforces_case_permissions_for_reads_edits_and_presentations(accounts):
    w, admin, alice, bob = accounts
    case = alice.post("/v1/cases", json={"title": "Private"}).json()
    path = f"/v1/cases/{case['id']}/workbench"
    ppt = f"/v1/cases/{case['id']}/presentations"
    payload = {"title": "Edit", "expected_revision": 0}
    assert bob.get(path).status_code == 404
    assert bob.put(path, json=payload).status_code == 404
    assert bob.post(ppt).status_code == 404
    alice.put(f"/v1/cases/{case['id']}/members", json={"username": "bob", "role": "viewer"})
    assert bob.get(path).status_code == 200
    assert bob.put(path, json=payload).status_code == 403
    assert bob.post(ppt).status_code == 403
    assert admin.get(path).status_code == 200

def test_timeline_uses_imported_messages_and_originals_without_analysis(accounts):
    w, admin, alice, bob = accounts
    case = alice.post("/v1/cases", json={"title": "Imported"}).json()
    cid = case["id"]
    evidence = alice.post(f"/v1/cases/{cid}/evidence/batch", files=upload_files()).json()["results"][0]["evidence"]
    w.repo.put("messages", cid+":m1", dict(id="m1", evidence_id=evidence["id"], text="Visible original words", timestamp=None, source_refs=[]), cid)
    w.repo.put("events", cid+":e1", dict(id="e1", title="Recorded event", timestamp="2024-02-01", source_refs=[]), cid)
    w.repo.put("events", cid+":old", dict(id="old", title="Old analysis event", analysis_run_id="inactive-run", source_refs=[]), cid)
    snapshot = alice.get(f"/v1/cases/{cid}/workbench").json()
    assert snapshot["case"]["active_analysis_run_id"] is None
    message = next(e for e in snapshot["timeline"] if e["id"] == "message:m1")
    assert message["title"] == "Visible original words" and message["timestamp"] is None
    assert message["evidence_ids"] == [evidence["id"]]
    assert snapshot["timeline"][0]["id"] == "event:e1"
    assert all(e["id"] != "event:old" for e in snapshot["timeline"])
    assert sum(e["kind"] == "evidence" for e in snapshot["timeline"]) == 2

def test_presentation_mock_reports_a_snapshot_without_generating_files_or_runs(accounts):
    w, admin, alice, bob = accounts
    case = alice.post("/v1/cases", json={"title": "Presentation"}).json()
    before = list(w.settings.data_dir.rglob("*"))
    response = alice.post(f"/v1/cases/{case['id']}/presentations", json={})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "mock" and result["provider"] == "mock" and result["download_url"] is None
    assert result["case_id"] == case["id"] and result["case_revision"] == 0
    assert not w.repo.list("analysis_runs") and not w.repo.list("egress_audit")
    assert not [p for p in w.settings.data_dir.rglob("*.pptx")]
