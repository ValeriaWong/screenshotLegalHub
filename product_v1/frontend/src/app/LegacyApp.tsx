import { SearchableSelect } from "../components/collections";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type CaseRecord } from "../api/client";
import { Button, Input } from "../components/ui";
import { Logo } from "../components/icons";
import { Feedback, FeatureBoundary } from "../components/feedback";
import { DetailRail, DetailRailProvider } from "../components/shell/DetailRail";
import { useI18n, type zh } from "../i18n";
import { useUrlState } from "../hooks/useUrlState";
import { useReducedMotion } from "../components/motion";
import { Overview } from "../features/cases/Overview";
import { Evidence } from "../features/evidence/Evidence";
import { Timeline } from "../features/timeline/Timeline";
import { Claims } from "../features/claims/Claims";
import { ProofMatrix } from "../features/proof-matrix/ProofMatrix";
import { Findings } from "../features/strategy/Findings";
import { Review } from "../features/review/Review";
import { Advanced } from "../features/runs/Advanced";
import { useUser } from "../features/auth/AuthGate";
import { ModelSettings } from "../features/settings/ModelSettings";
import { UserSettings } from "../features/settings/UserSettings";
const tabs = [
  "overview",
  "evidence",
  "timeline",
  "claims",
  "matrix",
  "contradictions",
  "gaps",
  "strategy",
  "review",
  "advanced",
  "users",
  "settings",
] as const;
export function LegacyApp() {
  const { t, locale, toggle } = useI18n();
  const client = useQueryClient();
  const user = useUser();
  const [caseId, setCaseId] = useUrlState("case");
  const [tab, setTab] = useUrlState("tab", "overview");
  const [title, setTitle] = useState("");
  const [caseSearch, setCaseSearch] = useState("");
  const [error, setError] = useState("");
  const reduced = useReducedMotion();
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
    setError("");
    try {
      const c = await fn();
      setCaseId(c.id);
      await client.invalidateQueries();
    } catch (e) {
      setError(String(e));
    }
  }
  const feature = () => {
    if (tab === "users") return <UserSettings />;
    if (tab === "settings") return <ModelSettings />;
    if (!selected) return caseId ? <Feedback state="error" error={t("caseUnavailable")} /> : <Feedback state="empty" />;
    const props = { caseId: selected.id, readOnly: selected.access_role === "viewer" };
    switch (tab) {
      case "evidence":
        return <Evidence {...props} />;
      case "timeline":
        return <Timeline {...props} />;
      case "claims":
        return <Claims {...props} />;
      case "matrix":
        return <ProofMatrix {...props} />;
      case "contradictions":
      case "gaps":
      case "strategy":
        return <Findings {...props} kind={tab} />;
      case "review":
        return <Review {...props} />;
      case "advanced":
        return <Advanced {...props} />;
      default:
        return <Overview {...props} />;
    }
  };
  return (
    <DetailRailProvider>
      <div className="app-shell" data-reduced-motion={reduced}>
        <header className="case-header">
          <div className="brand">
            <Logo />
            <div>
              <strong>ScreenshotLegal</strong>
              <span>{t("workspace")}</span>
            </div>
          </div>
          <div className="case-picker">
            <label>
              {t("searchCases")}
              <Input
                type="search"
                value={caseSearch}
                onChange={(e) => setCaseSearch(e.target.value)}
                placeholder={t("caseSearchHint")}
                aria-describedby="case-search-summary"
              />
            </label>
            <SearchableSelect label={<>
              {t("selectCase")}

            </>} value={selected?.id || ""}
                onChange={(e) => setCaseId(e.target.value)}
                aria-describedby="case-search-summary" searchable={false} filterKey={caseSearch} pinnedValue={selectedOutsideSearch ? selected?.id : undefined}>
                <option value="" disabled>
                  {t("emptyCases")}
                </option>
                {selectedOutsideSearch && (
                  <optgroup label={t("currentCaseOutsideSearch")}>
                    <option value={selected.id}>{selected.title}</option>
                  </optgroup>
                )}
                {matchingCases.map((c) => (
                  <option key={c.id} value={c.id} title={c.description}>
                    {c.title}
                  </option>
                ))}
              </SearchableSelect>
            <p className="case-picker-summary" id="case-search-summary" role="status">
              {cases.data ? <>
                {t("visibleCaseCount")}：{cases.data.length}
                {search && <> · {t("matchingCaseCount")}：{matchingCases.length}</>}
                {search && !matchingCases.length && <> · {t("noMatchingCases")}</>}
              </> : t(cases.isPending ? "loading" : "error")}
            </p>
          </div>
          <Button onClick={() => action(() => api("/demo", {}))}>
            {t("demo")}
          </Button>
          <Button onClick={toggle}>
            {locale === "en" ? "中文" : "English"}
          </Button>
          <Button onClick={() => setTab("users")}>{user?.display_name} · {user?.username}</Button>
          <Button onClick={async () => { try { await api("/auth/logout", {}); client.clear(); window.location.assign("/"); } catch (e) { setError(String(e)); } }}>{t("logout")}</Button>
        </header>
        <div className="draft-banner">{t("draft")}</div>
        <div className="workspace-layout">
          <nav aria-label={t("workspace")}>
            {tabs.map((key, i) => (
              <Button
                aria-current={tab === key ? "page" : undefined}
                key={key}
                onClick={() => setTab(key)}
              >
                <span className="nav-number">
                  {String(i + 1).padStart(2, "0")}
                </span>
                {t(key)}
              </Button>
            ))}
            <form
              className="new-case"
              onSubmit={(e) => {
                e.preventDefault();
                if (title.trim()) void action(() => api("/cases", { title }));
              }}
            >
              <label>
                {t("newCase")}
                <Input
                  aria-label={t("caseTitle")}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </label>
              <Button>{t("create")}</Button>
            </form>
          </nav>
          <main>
            <div className="workspace-title">
              <p className="eyebrow">{["users", "settings"].includes(tab) ? "ScreenshotLegal" : selected?.title || "ScreenshotLegal"}</p>
              <h1>
                {t(
                  (tabs.includes(tab as (typeof tabs)[number])
                    ? tab
                    : "overview") as keyof typeof zh,
                )}
              </h1>
              <p>
                {["users", "settings"].includes(tab) ? "" : selected?.description === "synthetic-demo-private-lending"
                  ? t("synthetic")
                  : t("reviewNotice")}
              </p>
            </div>
            {error && <Feedback state="error" error={error} />}
            {cases.isPending ? (
              <Feedback state="loading" />
            ) : cases.error ? (
              <Feedback
                state="error"
                error={cases.error.message}
                retry={() => cases.refetch()}
              />
            ) : (
              <FeatureBoundary key={tab + selected?.id} label={t("error")}>
                {feature()}
              </FeatureBoundary>
            )}
          </main>
          <DetailRail />
        </div>
      </div>
    </DetailRailProvider>
  );
}
