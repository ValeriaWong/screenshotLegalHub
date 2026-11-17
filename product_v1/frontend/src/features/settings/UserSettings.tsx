import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type User } from "../../api/client";
import { useUser } from "../auth/AuthGate";
import { Button, Card, Input, Badge } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { useI18n } from "../../i18n";

export function UserSettings() {
  const { t } = useI18n();
  const user = useUser();
  const client = useQueryClient();
  const [name, setName] = useState(user?.display_name || "");
  const [organization, setOrganization] = useState(user?.organization || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [account, setAccount] = useState({ username: "", password: "", display_name: "", role: "member" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/users"), enabled: user?.role === "admin" });
  async function action(fn: () => Promise<unknown>) {
    setBusy(true); setError(""); setSaved(false);
    try { await fn(); await client.invalidateQueries(); setSaved(true); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  return <>
    <Card><h2>{t("profile")}</h2><p>{user?.username} · {t(user?.role==="admin"?"admin":"member")}</p><p>平台管理员管理账号并访问全部案件。普通用户只能访问自己的案件和被共享的案件；案件所有者可授权编辑或只读访问。</p>
      <form className="settings-form" onSubmit={event => { event.preventDefault(); void action(() => api("/user", { display_name: name, organization }, "PUT")); }}>
        <label>{t("displayName")}<Input required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label>
        <label>{t("organization")}<Input maxLength={200} value={organization} onChange={e => setOrganization(e.target.value)} /></label>
        <Button disabled={busy}>{t("save")}</Button>
      </form>
    </Card>
    <Card><h2>{t("changePassword")}</h2><p>{t("passwordNotice")}</p>
      <form className="settings-form" onSubmit={event => { event.preventDefault(); void action(async () => {
        await api("/auth/password", { current_password: currentPassword, new_password: password }); client.clear(); window.location.assign("/");
      }); }}>
        <label>{t("currentPassword")}<Input required type="password" autoComplete="current-password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label>
        <label>{t("newPassword")}<Input required type="password" autoComplete="new-password" minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} /></label>
        <Button disabled={busy}>{t("changePassword")}</Button>
      </form>
    </Card>
    {user?.role === "admin" && <Card><h2>{t("manageUsers")}</h2>
      <form className="settings-form" onSubmit={event => { event.preventDefault(); void action(async () => { await api("/users", account); setAccount({ username: "", password: "", display_name: "", role: "member" }); }); }}>
        <label>{t("username")}<Input required minLength={3} maxLength={64} pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]+" autoComplete="off" value={account.username} onChange={e => setAccount({ ...account, username: e.target.value })} /></label>
        <label>{t("displayName")}<Input required value={account.display_name} onChange={e => setAccount({ ...account, display_name: e.target.value })} /></label>
        <label>{t("password")}<Input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={account.password} onChange={e => setAccount({ ...account, password: e.target.value })} /></label>
        <label>{t("role")}<select value={account.role} onChange={e => setAccount({ ...account, role: e.target.value })}><option value="member">{t("member")}</option><option value="admin">{t("admin")}</option></select></label>
        <Button disabled={busy}>{t("addUser")}</Button>
      </form>
      {users.error && <Feedback state="error" error={users.error.message} />}
      {<Paged items={users.data} label="用户账号" layout="block">{(pageItems) => pageItems.map(account => <div className="toolbar" key={account.id}><strong>{account.display_name} ({account.username})</strong><Badge>{account.role}</Badge><Badge>{t(account.enabled ? "enabled" : "disabled")}</Badge>
        <Button disabled={busy || account.id === user.id} onClick={() => action(() => api(`/users/${account.id}`, { role: account.role, enabled: !account.enabled }, "PUT"))}>{t(account.enabled ? "disableUser" : "enableUser")}</Button>
        <Button disabled={busy || account.id === user.id} onClick={() => action(() => api(`/users/${account.id}`, { role: account.role === "admin" ? "member" : "admin", enabled: account.enabled }, "PUT"))}>{t(account.role === "admin" ? "makeMember" : "makeAdmin")}</Button>
      </div>)}</Paged>}
    </Card>}
    {error && <Feedback state="error" error={error} />}{saved && <p role="status">{t("saved")}</p>}
  </>;
}
