import { SearchableSelect } from "../components/collections";
import { Workbench, type WorkbenchPage } from "../features/workbench/Workbench";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type CaseRecord } from "../api/client";
import { Button, Input } from "../components/ui";
import { Icon } from "../components/icons";
import { ProductHeader } from "../components/shell/ProductHeader";
import { Feedback, FeatureBoundary } from "../components/feedback";
import { DetailRail, DetailRailProvider } from "../components/shell/DetailRail";
import { useI18n } from "../i18n";
import { useUrlState } from "../hooks/useUrlState";
import { useReducedMotion } from "../components/motion";
import { useUser } from "../features/auth/AuthGate";
import { UserSettings } from "../features/settings/UserSettings";
const tabs = ["overview", "edit", "timeline", "presentation"] as const;
export function App() {
  const { t, locale, toggle } = useI18n();
  const client = useQueryClient();
  const user = useUser();
  const [caseId, setCaseId] = useUrlState("case");
  const [requestedTab, setTab] = useUrlState("tab", "overview");
  const tab: WorkbenchPage = tabs.includes(requestedTab as WorkbenchPage) ? requestedTab as WorkbenchPage : "overview";
  const [title, setTitle] = useState("");
  const [caseSearch, setCaseSearch] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const reduced = useReducedMotion();
  const [compact, setCompact] = useState(() => window.matchMedia("(max-width: 720px)").matches);
  const [caseToolsOpen, setCaseToolsOpen] = useState(false);
  const [newCaseOpen, setNewCaseOpen] = useState(false);
  const mainRef = useRef<HTMLElement>(null);
  const previousTab = useRef(tab);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 720px)");
    const update = () => setCompact(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (previousTab.current !== tab) mainRef.current?.focus({ preventScroll: true });
    previousTab.current = tab;
  }, [tab]);
  const cases = useQuery({
    queryKey: ["cases"],
    queryFn: () => api<CaseRecord[]>("/cases"),
  });
  const selected = caseId ? cases.data?.find((c) => c.id === caseId) : cases.data?.[0];
  const search = caseSearch.trim().toLowerCase();
  const matchingCases = (cases.data ?? []).filter((c) =>
    `${c.title}\n${c.description ?? ""}`.toLowerCase().includes(search),
  );
  const selectedOutsideSearch = selected && !matchingCases.some((c) => c.id === selected.id);
  async function action(fn: () => Promise<CaseRecord>) {
    if (creating) return;
    setCreating(true); setError("");
    try {
      const c = await fn();
      setCaseId(c.id); setTitle(""); setTab("overview");
      await client.invalidateQueries();
    } catch (e) {
      setError(String(e));
    } finally { setCreating(false); }
  }
  const feature = () => {
    if (!selected) return caseId ? <Feedback state="error" error={t("caseUnavailable")} /> : <Feedback state="empty" />;
    return <Workbench caseId={selected.id} userId={user?.id || "local"} page={tab} />;
  };
  if (new URLSearchParams(location.search).get("account")==="1") return <div className="app-shell"><ProductHeader product="workbench" english={locale==="en"}><a href="/">{locale==="en"?"Back to workspace":"返回用户工作台"}</a></ProductHeader><main className="account-settings-page"><h1>{locale==="en"?"Account & permissions":"账号与权限"}</h1><UserSettings/></main></div>;
  return (
    <DetailRailProvider>
      <div className="app-shell mvp-shell" data-reduced-motion={reduced}>
        <a className="skip-link" href="#workspace-main">{locale === "en" ? "Skip to workspace" : "跳转到工作区"}</a>
        <ProductHeader product="workbench" english={locale === "en"}>
          <Button variant="ghost" onClick={toggle}>{locale === "en" ? "中文" : "English"}</Button>
          <span className="account-name" title={user?.username}><span className="account-avatar" aria-hidden="true">{(user?.display_name || user?.username || "SL").slice(0, 1)}</span>{user?.display_name || user?.username}</span>
          <Button variant="ghost" onClick={async () => { try { await api("/auth/logout", {}); client.clear(); window.location.assign("/"); } catch (e) { setError(String(e)); } }}><Icon name="logout" size={16} />{t("logout")}</Button>
        </ProductHeader>
        <div className="context-bar">
          <span><Icon name="folder" size={16} />{t("workspace")}<span className="context-separator" aria-hidden="true">/</span><strong>{t(tab === "timeline" ? "evidenceTimeline" : tab)}</strong></span>
          <div className="context-links"><a href="/review.html?audit=1&audit_product=workbench"><Icon name="history" size={15} />{locale === "en" ? "Activity log" : "操作审计"}</a>{user?.role === "admin" && <a href="/console.html?tab=settings">{t("legacyConsole")}</a>}</div>
        </div>
        <div className="workspace-layout">
          <nav className="case-sidebar" aria-label={t("workspace")}>
            <details className="case-tools" open={!compact || caseToolsOpen} onToggle={e => { if (compact) setCaseToolsOpen(e.currentTarget.open); }}><summary><Icon name="folder" size={17} /><span>{selected?.title || t("selectCase")}</span></summary>
            <p className="sidebar-label">{locale === "en" ? "CASE FILES" : "案件档案"}</p>
            <div className="case-picker">
              <label>{t("searchCases")}<Input type="search" value={caseSearch} onChange={(e) => setCaseSearch(e.target.value)} placeholder={t("caseSearchHint")} aria-describedby="case-search-summary" /></label>
              <SearchableSelect label={<>{t("selectCase")}

              </>} value={selected?.id || ""} onChange={(e) => setCaseId(e.target.value)} aria-describedby="case-search-summary" searchable={false} filterKey={caseSearch} pinnedValue={selectedOutsideSearch ? selected?.id : undefined}>
                  <option value="" disabled>{t("emptyCases")}</option>
                  {selectedOutsideSearch && <optgroup label={t("currentCaseOutsideSearch")}><option value={selected.id}>{selected.title}</option></optgroup>}
                  {matchingCases.map((c) => <option key={c.id} value={c.id} title={c.description}>{c.title}</option>)}
                </SearchableSelect>
              <p className="case-picker-summary" id="case-search-summary" role="status">{cases.data ? <>{t("visibleCaseCount")}：{cases.data.length}{search && <> · {t("matchingCaseCount")}：{matchingCases.length}</>}{search && !matchingCases.length && <> · {t("noMatchingCases")}</>}</> : t(cases.isPending ? "loading" : "error")}</p>
            </div>
            </details>
            <p className="sidebar-label sidebar-section-label">{locale === "en" ? "CASE WORKSPACE" : "案件工作区"}</p>
            {tabs.map((key, i) => <Button aria-current={tab === key ? "page" : undefined} key={key} onClick={() => setTab(key)}><span className="nav-number">{String(i + 1).padStart(2, "0")}</span><Icon name={key} size={19} /><span className="nav-label">{t(key === "timeline" ? "evidenceTimeline" : key)}</span></Button>)}
            <details className="new-case-tools" open={!compact || newCaseOpen} onToggle={e => { if (compact) setNewCaseOpen(e.currentTarget.open); }}><summary>{t("newCase")}</summary>
            <form className="new-case" onSubmit={(e) => { e.preventDefault(); if (title.trim()) void action(() => api("/cases", { title })); }}>
              <label>{t("newCase")}<Input aria-label={t("caseTitle")} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} disabled={creating} /></label>
              <Button disabled={creating} aria-busy={creating}>{creating ? t("loading") : t("create")}</Button>
            </form></details>
            <div className="sidebar-footnote"><Icon name="scales" size={19} /><span>ScreenshotLegal<small>{locale === "en" ? "Evidence · Context · Insight" : "证据 · 脉络 · 洞察"}</small></span></div>
          </nav>
          <main id="workspace-main" ref={mainRef} tabIndex={-1}>
            <div className="workspace-title">
              <p className="eyebrow">{locale === "en" ? "CASE WORKBENCH" : "CASE WORKBENCH · 案件工作台"}</p>
              <h1>{t(tab === "timeline" ? "evidenceTimeline" : tab)}</h1>
              <p className="workspace-case-name"><Icon name="folder" size={16} />{selected?.title || "ScreenshotLegal"}</p>
              <p>{t("mvpWorkspaceHint")}</p>
            </div>
            {error && <Feedback state="error" error={error} />}
            {cases.isPending ? <Feedback state="loading" /> : cases.error ? <Feedback state="error" error={cases.error.message} retry={() => cases.refetch()} /> : <FeatureBoundary key={tab + selected?.id} label={t("error")}>{feature()}</FeatureBoundary>}
          </main>
          <DetailRail />
        </div>
      </div>
    </DetailRailProvider>
  );
}
