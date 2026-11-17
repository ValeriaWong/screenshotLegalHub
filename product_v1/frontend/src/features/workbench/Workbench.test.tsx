import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "../../i18n";
import { Workbench } from "./Workbench";
import { draftKey } from "./drafts";
const { fakeApi } = vi.hoisted(() => ({ fakeApi: vi.fn() }));
vi.mock("../../api/client", async importOriginal => ({ ...await importOriginal<object>(), api: fakeApi }));
const record = { id: "c", title: "Case", description: "Source metadata", summary: "", notes: "", revision: 0, created_at: "2026-01-01", access_role: "owner" };
const snapshot = { case: record, evidence: [{ id: "ev.1", filename: "chat.png", kind: "image" }], timeline: [{ id: "message:m", kind: "message", title: "Visible words", timestamp: null, evidence_ids: ["ev.1"], source_refs: [] }] };
function show(page: "overview" | "edit" | "timeline" | "presentation") {
  localStorage.setItem("locale", "zh-CN");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><I18nProvider><Workbench caseId="c" userId="alice" page={page} /></I18nProvider></QueryClientProvider>);
}
afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear(); });
it("restores account-scoped drafts and clears them only after a successful save", async () => {
  localStorage.setItem(draftKey("alice", "c"), JSON.stringify({ title: "Recovered", summary: "Draft summary", notes: "Draft note", expected_revision: 0 }));
  fakeApi.mockImplementation(async (path, body) => path === "/cases/c/workbench" && body ? { ...record, ...body, revision: 1 } : snapshot);
  show("edit");
  expect(await screen.findByLabelText("案件名称")).toHaveValue("Recovered");
  expect(screen.getByText("已恢复本机未保存的草稿。")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("工作备注"), { target: { value: "New note" } });
  expect(JSON.parse(localStorage.getItem(draftKey("alice", "c"))!).notes).toBe("New note");
  fireEvent.click(screen.getByRole("button", { name: "保存" }));
  await screen.findByText("案件信息已保存。");
  expect(localStorage.getItem(draftKey("alice", "c"))).toBeNull();
  expect(fakeApi).toHaveBeenCalledWith("/cases/c/workbench", expect.objectContaining({ expected_revision: 0, notes: "New note" }), "PUT");
});
it("retains a local draft after a failed save", async () => {
  fakeApi.mockImplementation(async (_path, body) => { if (body) throw new Error("Case has changed"); return snapshot; });
  show("edit");
  fireEvent.change(await screen.findByLabelText("工作备注"), { target: { value: "Keep me" } });
  fireEvent.click(screen.getByRole("button", { name: "保存" }));
  await screen.findByText(/Case has changed/);
  expect(JSON.parse(localStorage.getItem(draftKey("alice", "c"))!).notes).toBe("Keep me");
  expect(screen.getByLabelText("工作备注")).toHaveValue("Keep me");
});
it("shows undated evidence and its original file without requiring an analysis run", async () => {
  fakeApi.mockResolvedValue(snapshot);
  show("timeline");
  expect(await screen.findByRole("img", { name: "chat.png" })).toHaveAttribute("src", "/v1/cases/c/evidence/ev.1/file");
  expect(screen.queryByText("Visible words")).not.toBeInTheDocument();
  expect(screen.getByText("未注明时间", { selector: "time" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看原图" })).toHaveAttribute("href", "/v1/cases/c/evidence/ev.1/file");
});
it("labels presentation generation as a simulation and exposes no download link", async () => {
  fakeApi.mockImplementation(async path => path.endsWith("/presentations") ? { status: "mock", case_revision: 0 } : snapshot);
  show("presentation");
  await screen.findByRole("heading", { name: "生成 PPT" });
  fireEvent.click(screen.getByRole("button", { name: "生成 PPT" }));
  await screen.findByText(/模拟完成，尚未生成 PPT 文件/);
  expect(fakeApi).toHaveBeenCalledWith("/cases/c/presentations", {});
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
it("groups messages by image, excludes documents, and orders images using their evidence times", async () => {
  fakeApi.mockResolvedValue({ ...snapshot, evidence: [
    ...snapshot.evidence,
    { id: "ev.2", filename: "earlier.png", kind: "image" },
    { id: "doc", filename: "contract.pdf", kind: "document", mime_type: "application/pdf" },
  ], timeline: [
    { ...snapshot.timeline[0], timestamp: "2026-02-01T12:00:00" },
    { ...snapshot.timeline[0], id: "message:other", timestamp: "2026-02-02T12:00:00" },
    { ...snapshot.timeline[0], id: "message:earlier", evidence_ids: ["ev.2"], timestamp: "2026-01-01T12:00:00" },
  ] });
  show("timeline");
  const images = await screen.findAllByRole("img");
  expect(images.map(img => img.getAttribute("alt"))).toEqual(["earlier.png", "chat.png"]);
  expect(screen.getByText("2026-02-01T12:00:00 — 2026-02-02T12:00:00")).toBeInTheDocument();
  expect(screen.queryByText("contract.pdf")).not.toBeInTheDocument();
  expect(screen.queryByText("Visible words")).not.toBeInTheDocument();
});
