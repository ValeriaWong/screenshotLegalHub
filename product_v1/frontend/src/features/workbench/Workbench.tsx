import { CaseMembers } from "../cases/CaseMembers";
import { DocumentWorkbench } from "./DocumentWorkbench";
import { Paged } from "../../components/collections";
import { ImageTimeline } from "./ImageTimeline";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type CaseRecord } from "../../api/client";
import type { components } from "../../api/schema";
import { Card, Button, Input, Badge } from "../../components/ui";
import { Icon } from "../../components/icons";
import { Feedback } from "../../components/feedback";
import { useI18n } from "../../i18n";
import { draftKey, readDraft, saveDraft, clearDraft, type CaseEdit } from "./drafts";
type Snapshot = components["schemas"]["WorkbenchSnapshot"];
type Preview = components["schemas"]["PresentationPreview"];
export type WorkbenchPage = "overview" | "edit" | "timeline" | "presentation";
export function Workbench({ caseId, userId, page }: { caseId: string; userId: string; page: WorkbenchPage }) {
  const { t } = useI18n();
  const query = useQuery({ queryKey: ["workbench", caseId], queryFn: () => api<Snapshot>("/cases/" + caseId + "/workbench") });
  if (query.isPending) return <Feedback state="loading" />;
  if (query.error) return <Feedback state="error" error={query.error.message} retry={() => query.refetch()} />;
  const snapshot = query.data;
  if (page === "edit") return <Editor key={userId + caseId} snapshot={snapshot} userId={userId} reload={async () => { const fresh = await query.refetch(); if (!fresh.data || fresh.error) throw fresh.error || new Error(t("error")); return fresh.data.case; }} />;
  if (page === "timeline") return <ImageTimeline key={caseId} snapshot={snapshot} />;
  if (page === "presentation") return <Presentation key={caseId} snapshot={snapshot} />;
  return <Overview snapshot={snapshot} userId={userId} />;
}
function Overview({ snapshot, userId }: { snapshot: Snapshot; userId: string }) {
  const { t } = useI18n();
  const [membersOpen,setMembersOpen]=useState(false);
  return <>
    <p className="lede">{t("mvpDescription")}</p>
    <div className="stats">{[[t("evidence"), snapshot.evidence.length], [t("timelineMessages"), snapshot.timeline.filter(e => e.kind === "message").length], [t("timelineEvents"), snapshot.timeline.filter(e => e.kind === "event").length], [t("savedRevision"), snapshot.case.revision ?? 0]].map(([label, value]) => <Card key={label}><span>{label}</span><strong>{value}</strong></Card>)}</div>
    <Card><h2>{t("caseSummary")}</h2><p className="workbench-prose">{snapshot.case.summary || t("noSummary")}</p><h3>{t("workNotes")}</h3><p className="workbench-prose">{snapshot.case.notes || t("noNotes")}</p></Card>
    <Card><h2>{t("evidence")}</h2>{snapshot.evidence.length ? <ul className="workbench-evidence">{<Paged items={snapshot.evidence} label="案件证据" layout="list" resetKey={snapshot.case.id} pageSize={20}>{(pageItems) => pageItems.map(item => <li key={item.id}><Icon name="file" size={18} /><a href={"/v1/cases/" + snapshot.case.id + "/evidence/" + item.id + "/file"} target="_blank" rel="noreferrer">{item.filename}</a><Badge>{item.kind}</Badge></li>)}</Paged>}</ul> : <p>{t("empty")}</p>}</Card>
    <details className="case-access-panel" onToggle={e=>setMembersOpen(e.currentTarget.open)}><summary>案件成员与权限</summary>{membersOpen && <CaseMembers caseId={snapshot.case.id}/>}</details>
    <DocumentWorkbench key={snapshot.case.id} caseId={snapshot.case.id} userId={userId} readOnly={snapshot.case.access_role === "viewer"} evidence={snapshot.evidence} />
  </>;
}
function Editor({ snapshot, userId, reload }: { snapshot: Snapshot; userId: string; reload: () => Promise<CaseRecord> }) {
  const { t } = useI18n();
  const client = useQueryClient();
  const key = draftKey(userId, snapshot.case.id);
  const fromCase = (c: CaseRecord): CaseEdit => ({ title: c.title, summary: c.summary ?? "", notes: c.notes ?? "", expected_revision: c.revision ?? 0 });
  const [form, setForm] = useState<CaseEdit>(() => readDraft(key) || fromCase(snapshot.case));
  const [notice, setNotice] = useState(() => readDraft(key) ? "draftRestored" : "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const readOnly = snapshot.case.access_role === "viewer";
  const update = (patch: Partial<CaseEdit>) => { const next = { ...form, ...patch }; setForm(next); setNotice(saveDraft(key, next) ? "draftCached" : "draftCacheFailed"); };
  return <Card><h2>{t("editCase")}</h2><p>{t("caseEditNotice")}</p>{readOnly && <p>{t("readOnly")}</p>}
    <form className="settings-form" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError("");
      try {
        const saved = await api<CaseRecord>("/cases/" + snapshot.case.id + "/workbench", form, "PUT");
        setForm(fromCase(saved)); clearDraft(key); setNotice("caseSaved");
        client.setQueryData<Snapshot>(["workbench", snapshot.case.id], current => current ? { ...current, case: saved } : current);
        await client.invalidateQueries({ queryKey: ["cases"] });
      } catch (e) { setError(String(e)); } finally { setBusy(false); }
    }}>
      <label>{t("caseTitle")}<Input required maxLength={200} disabled={readOnly || busy} value={form.title} onChange={e => update({ title: e.target.value })} /></label>
      <label>{t("caseSummary")}<textarea aria-label={t("caseSummary")} maxLength={10000} disabled={readOnly || busy} value={form.summary} onChange={e => update({ summary: e.target.value })} /></label>
      <label>{t("workNotes")}<textarea aria-label={t("workNotes")} maxLength={50000} disabled={readOnly || busy} value={form.notes} onChange={e => update({ notes: e.target.value })} /></label>
      <div className="toolbar"><Button variant="primary" disabled={readOnly || busy} aria-busy={busy}>{t(busy ? "saving" : "save")}</Button><Button type="button" disabled={busy} onClick={async () => { setBusy(true); setError(""); try { const current = await reload(); setForm(fromCase(current)); clearDraft(key); setNotice(""); } catch (e) { setError(String(e)); } finally { setBusy(false); } }}>{t("discardLocalDraft")}</Button></div>
    </form>
    {notice && <p role="status">{t(notice as "draftRestored")}</p>}{error && <Feedback state="error" error={error} />}
  </Card>;
}
function Presentation({ snapshot }: { snapshot: Snapshot }) {
  const { t } = useI18n();
  const [result, setResult] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <Card><h2>{t("generatePpt")}</h2><p>{t("pptMockNotice")}</p><p>{snapshot.case.title} · {t("evidence")} {snapshot.evidence.length} · {t("timeline")} {snapshot.timeline.length}</p>
    <Button variant="primary" aria-busy={busy} disabled={busy || snapshot.case.access_role === "viewer"} onClick={async () => { setBusy(true); setError(""); setResult(null); try { setResult(await api<Preview>("/cases/" + snapshot.case.id + "/presentations", {})); } catch (e) { setError(String(e)); } finally { setBusy(false); } }}>{t(busy ? "pptPreparing" : "generatePpt")}</Button>
    {result && <p role="status">{t("pptMockComplete")} · {t("savedRevision")} {result.case_revision}</p>}{error && <Feedback state="error" error={error} />}
  </Card>;
}
