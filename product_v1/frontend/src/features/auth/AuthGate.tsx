import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type User } from "../../api/client";
import { Button, Card, Input } from "../../components/ui";
import { Logo } from "../../components/icons";
import { Feedback } from "../../components/feedback";
import { useI18n } from "../../i18n";

const UserContext = createContext<User | null>(null);
export const useUser = () => useContext(UserContext);

export function AuthGate({ children }: { children: ReactNode }) {
  const { t, locale } = useI18n();
  const client = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const status = useQuery({ queryKey: ["auth-status"], queryFn: () => api<{ initialized: boolean }>("/auth/status"), retry: false });
  const me = useQuery({ queryKey: ["auth-me"], retry: false, queryFn: async () => {
    try { return await api<User>("/auth/me"); }
    catch (e) { if (e instanceof ApiError && e.status === 401) return null; throw e; }
  }});
  useEffect(() => {
    const expire = () => { client.clear(); window.location.assign("/"); };
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, [client]);
  if (status.isPending || me.isPending) return <Feedback state="loading" />;
  if (status.error || me.error) return <Feedback state="error" error={String(status.error || me.error)} retry={() => { void status.refetch(); void me.refetch(); }} />;
  if (me.data) return <UserContext.Provider value={me.data}>{children}</UserContext.Provider>;
  const setup = !status.data?.initialized;
  return <main className="auth-screen"><section className="auth-intro"><Logo /><p className="eyebrow">LEGAL INTELLIGENCE WORKSPACE</p><h1>ScreenshotLegal</h1><p className="auth-statement">{locale === "en" ? <>Evidence in order.<br />Insight in context.</> : <>让证据有序，<br />让判断有据。</>}</p><p>{locale === "en" ? "Organize case materials, trace evidence and review every detail in context." : "整理案件材料，追溯原始证据，在完整的事实脉络中开展工作。"}</p></section><Card>
    <h2>{t(setup ? "setupAdmin" : "login")}</h2>
    <p>{t(setup ? "setupNotice" : "loginNotice")}</p>
    <form className="settings-form" onSubmit={async (event) => {
      event.preventDefault(); setBusy(true); setError("");
      try {
        const user = await api<User>(setup ? "/auth/setup" : "/auth/login", { username, password, ...(setup ? { display_name: name } : {}) });
        setPassword(""); client.clear(); client.setQueryData(["auth-me"], user); await client.invalidateQueries();
      } catch (e) { setError(String(e)); } finally { setBusy(false); }
    }}>
      <label>{t("username")}<Input required autoComplete="username" minLength={3} maxLength={64} pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]+" value={username} onChange={e => setUsername(e.target.value)} /></label>
      {setup && <label>{t("displayName")}<Input required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label>}
      <label>{t("password")}<Input required type="password" autoComplete={setup ? "new-password" : "current-password"} minLength={setup ? 12 : undefined} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} /></label>
      <Button variant="primary" disabled={busy} aria-busy={busy}>{t(busy ? "loading" : setup ? "setupAdmin" : "login")}</Button>
    </form>{error && <Feedback state="error" error={error} />}
  </Card></main>;
}
