"""End-user use cases, separate from research, dataset correction and evaluation."""
from uuid import uuid4
from screenshotlegal.application.services.auth import AuthError
from screenshotlegal.domain.common.models import CaseRecord, now
from screenshotlegal.domain.workbench import TimelineEntry, WorkbenchSnapshot, PresentationPreview
from screenshotlegal.infrastructure.db.models import MODELS
from .operation_events import operation

class MockPresentationGenerator:
    def generate(self, snapshot):
        return PresentationPreview(request_id=str(uuid4()), case_id=snapshot.case.id,
            case_revision=snapshot.case.revision, evidence_count=len(snapshot.evidence),
            timeline_count=len(snapshot.timeline),
            message="Simulation complete. A presentation service has not been connected; no PPT file was generated.")

class UserWorkbench:
    def __init__(self, workspace, auth, presentations=None):
        self.workspace, self.auth = workspace, auth
        self.repo = workspace.repo
        self.presentations = presentations or MockPresentationGenerator()

    def snapshot(self, actor, case_id):
        case = self.auth.access(actor, case_id)
        evidence = self.workspace.evidence(case_id)
        evidence_ids = {e["id"] for e in evidence}
        refs = {r["id"]: r for r in self.repo.list("source_refs", case_id=case_id)}
        messages = self.workspace.active_messages(case_id)
        active_run = case.get("active_analysis_run_id")
        events = [e for e in self.repo.list("events", case_id=case_id)
                  if not e.get("analysis_run_id") or e.get("analysis_run_id") == active_run]
        entries = []
        for kind, rows in (("event", events), ("message", messages)):
            for row in rows:
                details = row.get("details") or {}
                source_ids = [rid for rid in row.get("source_refs", []) if rid in refs]
                linked = [refs[rid]["evidence_id"] for rid in source_ids if refs[rid].get("evidence_id") in evidence_ids]
                if row.get("evidence_id") in evidence_ids:
                    linked.append(row["evidence_id"])
                entries.append(TimelineEntry(id=kind+":"+row["id"], kind=kind,
                    title=row.get("text") or row.get("title") or details.get("text") or row["id"],
                    timestamp=row.get("timestamp") or details.get("timestamp"),
                    time_label=row.get("time_label") or details.get("time_label"),
                    source_refs=source_ids, evidence_ids=list(dict.fromkeys(linked)),
                    review_status=row.get("review_status", "unreviewed")))
        for item in evidence:
            entries.append(TimelineEntry(id="evidence:"+item["id"], kind="evidence",
                title=item["filename"], evidence_ids=[item["id"]] if item["id"] in evidence_ids else []))
        entries.sort(key=lambda entry: (not bool(entry.timestamp), entry.timestamp or "", entry.kind, entry.id))
        return WorkbenchSnapshot(case=CaseRecord.model_validate(case), evidence=evidence, timeline=entries)

    def edit(self, actor, case_id, request):
        self.auth.access(actor, case_id, write=True)
        with self.repo.session.begin() as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            record = session.get(MODELS["cases"], case_id)
            if record is None:
                raise KeyError("Case not found")
            if self.auth.case_role(actor, record.body) not in {"owner", "editor"}:
                raise AuthError(403, "Insufficient case permission")
            if record.body.get("revision", 0) != request.expected_revision:
                raise AuthError(409, "Case has changed; reload before saving. Your local draft is retained.")
            old=record.body
            event=operation(actor.id,'workbench','case.edited','case',case_id,{k:dict(before=old.get(k),after=getattr(request,k)) for k in ['title','summary','notes'] if old.get(k)!=getattr(request,k)},'用户工作台显式保存')
            session.add(MODELS['run_events'](id=event['id'],case_id=case_id,run_id='operation-audit:'+actor.id,body=event))
            record.body = dict(record.body, title=request.title, summary=request.summary, notes=request.notes,
                               revision=request.expected_revision+1, updated_at=now())
        return CaseRecord.model_validate(self.auth.access(actor, case_id))

    def preview_presentation(self, actor, case_id):
        self.auth.access(actor, case_id, write=True)
        return self.presentations.generate(self.snapshot(actor, case_id))
