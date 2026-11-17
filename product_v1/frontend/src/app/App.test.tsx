import { render, screen, cleanup, fireEvent, within } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LegacyApp as App } from "./LegacyApp";
import { I18nProvider } from "../i18n";
const { fakeApi } = vi.hoisted(() => ({ fakeApi: vi.fn() }));
vi.mock("../api/client", async importOriginal => ({ ...await importOriginal<object>(), api: fakeApi }));
vi.mock("../features/cases/Overview", () => ({ Overview: ({ caseId }: { caseId: string }) => <div data-testid="selected-case">{caseId}</div> }));
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });
it("does not substitute another case when a shared link is inaccessible", async () => {
  history.replaceState({}, "", "/?case=foreign&tab=evidence");
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  fakeApi.mockResolvedValue([{ id: "own", title: "Own case", access_role: "owner" }]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><I18nProvider><App /></I18nProvider></QueryClientProvider>);
  expect(await screen.findByRole("alert")).toHaveTextContent("该案件不存在或你没有访问权限，请选择其他案件。");
  expect(screen.queryByLabelText("上传证据")).not.toBeInTheDocument();
  expect(fakeApi).not.toHaveBeenCalledWith("/cases/own/evidence");
});

function renderCases(records: { id: string; title: string; description?: string }[], caseId = "case-0") {
  history.replaceState({}, "", "/?case=" + caseId);
  localStorage.setItem("locale", "zh-CN");
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  fakeApi.mockImplementation((path: string) => Promise.resolve(path === "/cases" ? records : []));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><I18nProvider><App /></I18nProvider></QueryClientProvider>);
}

it("keeps all cases reachable while bounding each page of native options", async () => {
  renderCases(Array.from({ length: 205 }, (_, i) => ({
    id: "case-" + i,
    title: "案件 " + i,
    description: i % 2 ? "来源 round_006 · 版本 2.0.0 · 状态 verified" : "来源 round_003 · 版本 1.0.0 · 状态 source_gap",
  })));
  expect(await screen.findByText("可见案件总数：205")).toBeInTheDocument();
  const picker = screen.getByRole("combobox", { name: "选择案件" });
  expect(within(picker).getAllByRole("option")).toHaveLength(51);
  for (let page = 1; page < 5; page++) fireEvent.click(screen.getByRole("button", { name: "下一页：选择案件" }));
  expect(picker).toHaveValue("case-0");
  expect(within(picker).getAllByRole("option").length).toBeLessThanOrEqual(52);
  expect(within(picker).getByRole("option", { name: "案件 204" })).toBeInTheDocument();
  expect(fakeApi).toHaveBeenCalledWith("/cases");
});

it("searches case titles and descriptions including source, version and status", async () => {
  renderCases([
    { id: "case-0", title: "当前案件" },
    { id: "older", title: "Contract Alpha", description: "来源 round_003 · 版本 1.0.0 · 状态 source_gap" },
    { id: "newer", title: "Contract Beta", description: "来源 round_006 · 版本 2.0.0 · 状态 verified" },
  ]);
  await screen.findByText("可见案件总数：3");
  const search = screen.getByRole("searchbox", { name: "搜索案件" });
  const picker = screen.getByRole("combobox", { name: "选择案件" });
  for (const keyword of ["  ALPHA  ", "ROUND_003", "1.0.0", "source_gap"]) {
    fireEvent.change(search, { target: { value: keyword } });
    expect(within(picker).getByRole("option", { name: "Contract Alpha" })).toBeInTheDocument();
    expect(within(picker).queryByRole("option", { name: "Contract Beta" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("可见案件总数：3 · 匹配案件：1");
  }
  fireEvent.change(search, { target: { value: "" } });
  expect(within(picker).getAllByRole("option")).toHaveLength(4);
  expect(within(picker).getByRole("option", { name: "Contract Beta" })).toBeInTheDocument();
});

it("retains the current case while filtering and allows selecting a matching case", async () => {
  renderCases([
    { id: "case-0", title: "当前案件", description: "round_003" },
    { id: "match", title: "匹配案件", description: "round_006" },
  ]);
  await screen.findByText("可见案件总数：2");
  const search = screen.getByRole("searchbox", { name: "搜索案件" });
  const picker = screen.getByRole("combobox", { name: "选择案件" });
  fireEvent.change(search, { target: { value: "round_006" } });
  expect(picker).toHaveValue("case-0");
  expect(screen.getByTestId("selected-case")).toHaveTextContent("case-0");
  expect(within(picker).getByRole("group", { name: "当前选中（未匹配搜索）" })).toBeInTheDocument();
  expect(new URLSearchParams(location.search).get("case")).toBe("case-0");
  fireEvent.change(picker, { target: { value: "match" } });
  expect(screen.getByTestId("selected-case")).toHaveTextContent("match");
  expect(new URLSearchParams(location.search).get("case")).toBe("match");
  fireEvent.change(search, { target: { value: "不存在的关键词" } });
  expect(picker).toHaveValue("match");
  expect(screen.getByRole("status")).toHaveTextContent("匹配案件：0 · 没有匹配的案件");
  expect(screen.getByTestId("selected-case")).toHaveTextContent("match");
  expect(fakeApi.mock.calls.filter(([path]) => path === "/cases")).toHaveLength(1);
});
