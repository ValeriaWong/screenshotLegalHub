import { render, screen, fireEvent, waitFor, cleanup, within } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "../../i18n";
import { ModelSettings } from "./ModelSettings";
const { fakeApi } = vi.hoisted(() => ({ fakeApi: vi.fn() }));
vi.mock("../../api/client", async importOriginal => ({ ...await importOriginal<object>(), api: fakeApi }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it("edits a saved model without exposing or replacing its key, and tests connectivity", async () => {
  const model = { id: "m", name: "Saved vision", base_url: "https://unit.test/v1", model_name: "vision", supports_vision: true, allow_external_egress: true, has_api_key: true, is_default: true };
  fakeApi.mockImplementation(async path => path === "/settings/test-image" ? null : path === "/settings/models" ? [model] : path.endsWith("/test") ? { success: true, message: "OK", latency_ms: 5 } : model);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><I18nProvider><ModelSettings /></I18nProvider></QueryClientProvider>);
  await screen.findByText("Saved vision");
  fireEvent.click(screen.getByRole("button", { name: "编辑模型" }));
  expect(screen.getByLabelText("API Key")).toHaveValue("");
  expect(screen.getByLabelText("API Key")).toHaveAttribute("type", "password");
  fireEvent.click(screen.getByRole("button", { name: "保存" }));
  await waitFor(() => expect(fakeApi).toHaveBeenCalledWith("/settings/models/m", expect.objectContaining({ api_key: null }), "PUT"));
  await waitFor(() => expect(screen.getByRole("button", { name: "测试文本连通性" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "测试文本连通性" }));
  await screen.findByText(/连接成功/);
  expect(fakeApi).toHaveBeenCalledWith("/settings/models/m/test", {});
});


const repeatModel = { id: "repeat", name: "Repeat model", base_url: "https://unit.test/v1", model_name: "reasoning", supports_vision: true, allow_external_egress: true, has_api_key: true, is_default: true };
function renderSettings() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><I18nProvider><ModelSettings /></I18nProvider></QueryClientProvider>);
}

it("clears the previous result while retesting and recovers after a failed test", async () => {
  let attempts = 0;
  let finishSecond!: (result: { success: boolean; message: string; latency_ms: number }) => void;
  fakeApi.mockImplementation(async path => {
    if (path === "/settings/test-image") return null;
    if (path === "/settings/models") return [repeatModel];
    if (path.endsWith("/test")) {
      attempts += 1;
      if (attempts === 2) return new Promise(resolve => { finishSecond = resolve; });
      return { success: true, message: "OK", latency_ms: 5 };
    }
    return repeatModel;
  });
  renderSettings();
  const button = await screen.findByRole("button", { name: "测试文本连通性" });
  fireEvent.click(button);
  await screen.findByText(/连接成功/);
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(screen.queryByText(/连接成功/)).not.toBeInTheDocument();
  expect(screen.getByText(/正在测试连通性…/)).toBeInTheDocument();
  expect(button).toBeDisabled();
  expect(attempts).toBe(2);
  finishSecond({ success: false, message: "Model HTTP 429", latency_ms: 8 });
  await screen.findByText(/连接失败/);
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await screen.findByText(/连接成功/);
  expect(screen.queryByText(/连接失败/)).not.toBeInTheDocument();
  await waitFor(() => expect(button).toBeEnabled());
  expect(attempts).toBe(3);
});

it("removes stale success when a retest request fails", async () => {
  let attempts = 0;
  fakeApi.mockImplementation(async path => {
    if (path === "/settings/test-image") return null;
    if (path === "/settings/models") return [repeatModel];
    if (path.endsWith("/test")) {
      if (++attempts === 2) throw new Error("Synthetic network failure");
      return { success: true, message: "OK", latency_ms: 5 };
    }
    return repeatModel;
  });
  renderSettings();
  const button = await screen.findByRole("button", { name: "测试文本连通性" });
  fireEvent.click(button);
  await screen.findByText(/连接成功/);
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await screen.findByText(/Synthetic network failure/);
  expect(screen.queryByText(/连接成功/)).not.toBeInTheDocument();
  expect(screen.queryByText(/正在测试连通性…/)).not.toBeInTheDocument();
  expect(button).toBeEnabled();
});


it("sends the case image separately and preserves text success when the image test fails", async () => {
  const sample = { case_id: "case", evidence_id: "ev.image", case_title: "My case", filename: "chat.png" };
  fakeApi.mockImplementation(async (path, body) => {
    if (path === "/settings/models") return [repeatModel];
    if (path === "/settings/test-image") return sample;
    if (path.endsWith("/test")) return { success: body.mode !== "image", message: body.mode === "image" ? "Model HTTP 400" : "OK", latency_ms: 5 };
    return repeatModel;
  });
  renderSettings();
  const link = await screen.findByRole("link", { name: "My case · chat.png" });
  expect(link).toHaveAttribute("href", "/v1/cases/case/evidence/ev.image/file");
  const textButton = await screen.findByRole("button", { name: "测试文本连通性" });
  const imageButton = screen.getByRole("button", { name: "测试图片连通性" });
  fireEvent.click(textButton);
  await screen.findByText(/文本测试 · 连接成功/);
  await waitFor(() => expect(imageButton).toBeEnabled());
  fireEvent.click(imageButton);
  await screen.findByText(/图片测试 · 连接失败/);
  expect(screen.getByText(/文本测试 · 连接成功/)).toBeInTheDocument();
  expect(fakeApi).toHaveBeenCalledWith("/settings/models/repeat/test", { mode: "image", case_id: "case", evidence_id: "ev.image" });
});

it("keeps text testing enabled without a case image and disables image testing", async () => {
  fakeApi.mockImplementation(async path => path === "/settings/models" ? [repeatModel] : null);
  renderSettings();
  expect(await screen.findByRole("button", { name: "测试文本连通性" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "测试图片连通性" })).toBeDisabled();
  expect(screen.getByText(/案件中尚无可用图片/)).toBeInTheDocument();
});

it("orders persisted passes before untested and failed models and distinguishes text from image", async () => {
  const check = (success: boolean) => ({ success, checked_at: "2026-10-25T00:00:00Z", latency_ms: 5 });
  const models = [
    { ...repeatModel, id: "failed", name: "Failed model", connectivity: { text: check(false) } },
    { ...repeatModel, id: "untested", name: "Untested model", connectivity: {} },
    { ...repeatModel, id: "partial", name: "Partial model", connectivity: { text: check(true), image: check(false) } },
    { ...repeatModel, id: "passed", name: "Passed model", connectivity: { text: check(true), image: check(true) } },
  ];
  fakeApi.mockImplementation(async path => path === "/settings/models" ? models : null);
  const { container } = render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><I18nProvider><ModelSettings /></I18nProvider></QueryClientProvider>);
  await screen.findByText("Passed model");
  expect([...container.querySelectorAll("[data-model-id]")].map(el => el.getAttribute("data-model-id"))).toEqual(["passed","partial","untested","failed"]);
  const partial = screen.getByText("Partial model").closest("section")!;
  expect(within(partial).getByText("部分测试通过")).toBeInTheDocument();
  expect(within(partial).getByText("文本已连通")).toBeInTheDocument();
  expect(within(partial).getByText("图片未连通")).toBeInTheDocument();
  expect(screen.getByText("Untested model").closest("section")).toHaveTextContent("尚未测试");
});
it("moves a newly passed model forward and removes its pass label after a failed retest", async () => {
  let attempts = 0;
  const models = [{...repeatModel,id:"first",name:"Unverified first"}, {...repeatModel,id:"second",name:"Test this second",supports_vision:false}];
  fakeApi.mockImplementation(async path => path === "/settings/models" ? models : path.endsWith("/test") ? {success:++attempts === 1,message:"fixture",latency_ms:5} : null);
  const view=render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><I18nProvider><ModelSettings /></I18nProvider></QueryClientProvider>);
  const card=(await screen.findByText("Test this second")).closest("section")!;
  fireEvent.click(within(card).getByRole("button",{name:"测试文本连通性"}));
  await within(card).findByText("文本已连通");
  expect(view.container.querySelector("[data-model-id]")).toHaveAttribute("data-model-id","second");
  await waitFor(()=>expect(within(card).getByRole("button",{name:"测试文本连通性"})).toBeEnabled());
  fireEvent.click(within(card).getByRole("button",{name:"测试文本连通性"}));
  await within(card).findByText("文本未连通");
  expect(within(card).queryByText("测试已通过")).not.toBeInTheDocument();
  expect(view.container.querySelector("[data-model-id]")).toHaveAttribute("data-model-id","first");
});
