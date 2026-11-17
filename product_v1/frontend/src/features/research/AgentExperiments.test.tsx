import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AgentExperiments } from "./AgentExperiments";
import { api } from "../../api/client";
vi.mock("../../api/client", () => ({ api: vi.fn() }));
afterEach(cleanup);
beforeEach(() => {
  history.replaceState({}, "", "/evaluation.html?view=agents&case=c1");
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async (path: string) => {
    if (path === "/settings/models") return [{ id: "aiping", name: "已启用模型", model_name: "test", base_url: "https://www.aiping.cn/api/v1", allow_external_egress: true }];
    if (path === "/cases") return [{ id: "c1", title: "公开测试案件" }];
    if (path.includes("/documents")) return [{ id: "d1", filename: "原文.txt", status: "complete" }];
    if (path === "/evaluation/agent-methods") return { candidates: [{ id: "E00", reproduction_name: "e00_single_shot", title: "直接回答", priority: "P0", implementation_status: "implemented" }, { id: "E04", title: "形式验证", priority: "P1", implementation_status: "planned" }] };
    if (path === "/evaluation/agent-preview") return { input_digest: "frozen", sources: 1, estimated_call_ceiling: 4, methods: [{ id: "E00", maximum_model_calls: 1 }], limitations: [] };
    return [];
  });
});
function view() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AgentExperiments /></QueryClientProvider>); }
it("requires a fresh preview when experiment parameters change", async () => {
  view();
  await screen.findByText(/E00 · 直接回答/);
  expect(screen.getByLabelText(/E04 · 形式验证/)).toBeDisabled();
  expect(screen.getByText(/e00_single_shot/)).toBeInTheDocument();
  const preview = screen.getByRole("button", { name: "检查输入与预算" });
  fireEvent.submit(preview.closest("form")!);
  await screen.findByRole("button", { name: "启动离线演练" });
  const sent = vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/agent-preview")?.[1];
  expect(sent).toMatchObject({ case_id: "c1", model_id: "demo", allow_draft_matter: false });
  fireEvent.change(screen.getByLabelText("E09 辩论轮数"), { target: { value: "2" } });
  expect(screen.queryByRole("button", { name: "启动离线演练" })).not.toBeInTheDocument();
  expect(vi.mocked(api).mock.calls.filter(c => c[0] === "/evaluation/agent-runs" && c[1])).toHaveLength(0);
});
it("shows a failed preview without enabling model execution", async () => {
  view();await screen.findByText(/E00 · 直接回答/);
  vi.mocked(api).mockImplementation(async path => { if (path === "/evaluation/agent-preview") throw new Error("模板未复核"); return []; });
  fireEvent.submit(screen.getByRole("button", { name: "检查输入与预算" }).closest("form")!);
  await waitFor(() => expect(screen.getByText(/模板未复核/)).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "启动离线演练" })).not.toBeInTheDocument();
});

it("freezes explicit inference controls and invalidates preview after changes", async () => {
  view();
  await screen.findByRole("option", { name: /已启用模型/ });
  fireEvent.change(screen.getByLabelText("分析模型"), { target: { value: "aiping" } });
  fireEvent.change(screen.getByLabelText("思考模式"), { target: { value: "off" } });
  fireEvent.change(screen.getByLabelText("单次输出 token 上限"), { target: { value: "4000" } });
  fireEvent.submit(screen.getByRole("button", { name: "检查输入与预算" }).closest("form")!);
  await screen.findByRole("button", { name: "启动所选模型实验（按调用计费）" });
  expect(vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/agent-preview")?.[1]).toMatchObject({ inference_options: { enable_thinking: false }, budget: { max_output_per_call: 4000 } });
  fireEvent.change(screen.getByLabelText("思考模式"), { target: { value: "on" } });
  expect(screen.queryByRole("button", { name: "启动所选模型实验（按调用计费）" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("分析模型"), { target: { value: "demo" } });
  expect(screen.queryByLabelText("思考模式")).not.toBeInTheDocument();
});
