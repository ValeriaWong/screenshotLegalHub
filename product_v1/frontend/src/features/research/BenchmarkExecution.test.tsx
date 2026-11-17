import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BenchmarkExecution } from "./BenchmarkPanel";
import { api } from "../../api/client";
vi.mock("../../api/client", () => ({ api: vi.fn() }));
vi.mock("../auth/AuthGate", () => ({ useUser: () => ({ id: "test-user" }) }));
vi.mock("./benchmarkDrafts", () => ({ readDraft: async () => null, writeDraft: async () => {}, clearDraft: async () => {}, draftKey: (...parts: string[]) => parts.join(":") }));
afterEach(cleanup);
beforeEach(() => {
  history.replaceState({}, "", "/evaluation.html?benchmark=1");
  vi.mocked(api).mockReset();
  vi.mocked(api).mockImplementation(async path => {
    if (path === "/evaluation/task-prompts") return [{ id: "kp", name: "抽取", family: "kie", version: 1, markdown: "仅抽取原图", note: "test", parent_id: null }, { id: "vp", name: "全图问答", family: "vqa", version: 1, markdown: "仅根据原图作答", note: "test", parent_id: null }];
    if (path === "/evaluation/benchmark-runs") return [];
    return [];
  });
});
function view() { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><BenchmarkExecution dataset="test" selected={["kie"]} /></QueryClientProvider>); }
it("counts each native Self-Refine request and blocks an insufficient call budget", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E05" } });
  expect(screen.getByRole("status")).toHaveTextContent("最多需要 4 次调用");
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "4" } });
  fireEvent.change(screen.getByLabelText("本次运行名称"), { target: { value: "Self-Refine KIE" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeEnabled();
  fireEvent.submit(screen.getByRole("button", { name: "开始所选任务" }).closest("form")!);
  await waitFor(() => expect(vi.mocked(api).mock.calls.some(c => c[0] === "/evaluation/benchmark-runs" && c[1])).toBe(true));
  expect(vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/benchmark-runs" && c[1])?.[1]).toMatchObject({ method_id: "E05", method_attempts: 2, max_calls: 4, method_max_output_tokens: 6144 });
});
it("shows the native ReAct upper bound and refuses unsupported input tracks", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E01" } });
  expect(screen.getByRole("status")).toHaveTextContent("最多需要 14 次调用");
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "14" } });
  fireEvent.change(screen.getByLabelText("模型看什么"), { target: { value: "vqa_predicted_text" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  expect(vi.mocked(api).mock.calls.filter(c => c[0] === "/evaluation/benchmark-runs" && c[1])).toHaveLength(0);
});

it("requires saved KIE text for LightRAG and submits the actual dynamic budget", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E16" } });
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "20" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("模型看什么"), { target: { value: "vqa_predicted_text" } });
  await screen.findByRole("option", { name: /全图问答 · v1/ });
  expect(screen.getByRole("status")).toHaveTextContent("至少预留 4 次调用，本次上限 20 次");
  const input = screen.getByLabelText("上游 KIE 结果编号");
  expect(input).toBeRequired();
  fireEvent.change(input, { target: { value: "saved-kie-attempt" } });
  fireEvent.change(screen.getByLabelText("本次运行名称"), { target: { value: "LightRAG 全局问答" } });
  fireEvent.submit(screen.getByRole("button", { name: "开始所选任务" }).closest("form")!);
  await waitFor(() => expect(vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/benchmark-runs" && c[1])?.[1]).toMatchObject({ method_id: "E16", track: "vqa_predicted_text", upstream_attempt_id: "saved-kie-attempt", max_calls: 20 }));
});
it("recomputes the Reflexion action and reflection ceiling when attempts change", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E21" } });
  expect(screen.getByRole("status")).toHaveTextContent("最多需要 5 次调用");
  fireEvent.change(screen.getByLabelText("最多尝试次数"), { target: { value: "3" } });
  expect(screen.getByRole("status")).toHaveTextContent("最多需要 8 次调用");
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "7" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "8" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeEnabled();
});

it("offers CoA paper reimplementation only for frozen KIE text and submits a dynamic budget", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E14" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("模型看什么"), { target: { value: "vqa_predicted_text" } });
  await screen.findByRole("option", { name: /全图问答 · v1/ });
  expect(screen.getByRole("status")).toHaveTextContent("至少预留 2 次调用");
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "8" } });
  fireEvent.change(screen.getByLabelText("上游 KIE 结果编号"), { target: { value: "frozen-kie" } });
  fireEvent.change(screen.getByLabelText("本次运行名称"), { target: { value: "CoA 预测文本验证" } });
  fireEvent.submit(screen.getByRole("button", { name: "开始所选任务" }).closest("form")!);
  await waitFor(() => expect(vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/benchmark-runs" && c[1])?.[1]).toMatchObject({ method_id: "E14", track: "vqa_predicted_text", upstream_attempt_id: "frozen-kie", max_calls: 8 }));
});

it("selects L-MAD consensus or ranked voting with binary-text dynamic budget", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E09" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("模型看什么"), { target: { value: "vqa_predicted_text" } });
  await screen.findByRole("option", { name: /全图问答 · v1/ });
  expect(screen.getByRole("status")).toHaveTextContent("至少预留 10 次调用");
  fireEvent.change(screen.getByLabelText("L-MAD 决策协议"), { target: { value: "ranked" } });
  expect(screen.getByRole("status")).toHaveTextContent("至少预留 24 次调用");
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "36" } });
  fireEvent.change(screen.getByLabelText("上游 KIE 结果编号"), { target: { value: "saved-kie" } });
  fireEvent.change(screen.getByLabelText("本次运行名称"), { target: { value: "L-MAD 排名" } });
  fireEvent.submit(screen.getByRole("button", { name: "开始所选任务" }).closest("form")!);
  await waitFor(() => expect(vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/benchmark-runs" && c[1])?.[1]).toMatchObject({ method_id: "E09", method_protocol: "ranked", track: "vqa_predicted_text", max_calls: 36 }));
});

it("freezes LegalAgentBench controller selection and requires predicted text", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E23" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("模型看什么"), { target: { value: "vqa_predicted_text" } });
  await screen.findByRole("option", { name: /全图问答 · v1/ });
  expect(screen.getByRole("status")).toHaveTextContent("至少预留 6 次调用");
  fireEvent.change(screen.getByLabelText("LegalAgentBench 控制器"), { target: { value: "plan_and_solve" } });
  expect(screen.getByRole("status")).toHaveTextContent("至少预留 4 次调用");
  fireEvent.change(screen.getByLabelText("LegalAgentBench 控制器"), { target: { value: "plan_and_execute" } });
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "26" } });
  fireEvent.change(screen.getByLabelText("上游 KIE 结果编号"), { target: { value: "saved-kie" } });
  fireEvent.change(screen.getByLabelText("本次运行名称"), { target: { value: "LegalAgentBench 规划" } });
  fireEvent.submit(screen.getByRole("button", { name: "开始所选任务" }).closest("form")!);
  await waitFor(() => expect(vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/benchmark-runs" && c[1])?.[1]).toMatchObject({ method_id: "E23", method_variant: "plan_and_execute", track: "vqa_predicted_text", max_calls: 26 }));
});

it("offers JurisMA inference only with frozen KIE text and reserves its 29-call ceiling", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E18" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("模型看什么"), { target: { value: "vqa_predicted_text" } });
  await screen.findByRole("option", { name: /全图问答 · v1/ });
  expect(screen.getByRole("status")).toHaveTextContent("至少预留 29 次调用");
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "28" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "29" } });
  fireEvent.change(screen.getByLabelText("上游 KIE 结果编号"), { target: { value: "saved-kie" } });
  fireEvent.change(screen.getByLabelText("本次运行名称"), { target: { value: "JurisMA 推理分支" } });
  fireEvent.submit(screen.getByRole("button", { name: "开始所选任务" }).closest("form")!);
  await waitFor(() => expect(vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/benchmark-runs" && c[1])?.[1]).toMatchObject({ method_id: "E18", track: "vqa_predicted_text", upstream_attempt_id: "saved-kie", max_calls: 29 }));
});

it("offers GraphRAG author global search only for frozen text and reserves its indexing budget", async () => {
  view(); await screen.findByRole("option", { name: /抽取 · v1/ });
  fireEvent.change(screen.getByLabelText("答题方法"), { target: { value: "E24" } });
  expect(screen.getByRole("button", { name: "开始所选任务" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("模型看什么"), { target: { value: "vqa_predicted_text" } });
  await screen.findByRole("option", { name: /全图问答 · v1/ });
  expect(screen.getByRole("status")).toHaveTextContent("至少预留 40 次调用");
  fireEvent.change(screen.getByLabelText("本次最多调用次数"), { target: { value: "40" } });
  fireEvent.change(screen.getByLabelText("上游 KIE 结果编号"), { target: { value: "saved-kie" } });
  fireEvent.change(screen.getByLabelText("本次运行名称"), { target: { value: "GraphRAG 原索引流程" } });
  fireEvent.submit(screen.getByRole("button", { name: "开始所选任务" }).closest("form")!);
  await waitFor(() => expect(vi.mocked(api).mock.calls.find(c => c[0] === "/evaluation/benchmark-runs" && c[1])?.[1]).toMatchObject({ method_id: "E24", track: "vqa_predicted_text", upstream_attempt_id: "saved-kie", max_calls: 40 }));
});
