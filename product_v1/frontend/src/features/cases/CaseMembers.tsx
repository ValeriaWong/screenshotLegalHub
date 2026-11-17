import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type CaseRecord } from "../../api/client";
import { Button, Card, Input } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { useI18n } from "../../i18n";

export function CaseMembers({ caseId }: { caseId: string }) {
  const { t } = useI18n(); const client = useQueryClient();
  const info = useQuery({ queryKey: ["case", caseId], queryFn: () => api<CaseRecord>(`/cases/${caseId}`) });
  const members = useQuery({ queryKey: ["members", caseId], queryFn: () => api<{ username: string; role: string }[]>(`/cases/${caseId}/members`) });
  const [username, setUsername] = useState(""); const [role, setRole] = useState("viewer");
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function share(username: string, role: string) {
    setBusy(true); setError("");
    try { await api(`/cases/${caseId}/members`, { username, role }, "PUT"); await client.invalidateQueries(); setUsername(""); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  return <Card><h2>{t("caseMembers")}</h2><p>{t("caseOwner")}: {info.data?.owner_id}</p>
    {info.data?.access_role === "owner" && <form className="toolbar" onSubmit={e => { e.preventDefault(); void share(username, role); }}>
      <label>{t("username")}<Input required value={username} onChange={e => setUsername(e.target.value)} /></label>
      <label>{t("role")}<select value={role} onChange={e => setRole(e.target.value)}><option value="viewer">{t("viewer")}</option><option value="editor">{t("editor")}</option></select></label>
      <Button disabled={busy}>{t("shareCase")}</Button>
    </form>}
    {<Paged items={members.data} label="案件成员" layout="block">{(pageItems) => pageItems.map(member => <div className="toolbar" key={member.username}><span>{member.username} · {t(member.role === "viewer" ? "viewer" : "editor")}</span>{info.data?.access_role === "owner" && <><label>{member.username} 的案件权限<select aria-label={member.username+" 的案件权限"} disabled={busy} value={member.role} onChange={e=>share(member.username,e.target.value)}><option value="viewer">{t("viewer")}</option><option value="editor">{t("editor")}</option></select></label><Button disabled={busy} onClick={() => share(member.username, "remove")}>{t("removeMember")}</Button></>}</div>)}</Paged>}
    {error && <Feedback state="error" error={error} />}{members.error && <Feedback state="error" error={members.error.message} />}
  </Card>;
}
