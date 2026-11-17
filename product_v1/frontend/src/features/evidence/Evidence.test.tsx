import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Evidence } from "./Evidence";
import { I18nProvider } from "../../i18n";
const { fakeApi, batch } = vi.hoisted(() => ({ fakeApi: vi.fn(), batch: vi.fn() }));
vi.mock("../../api/client", async importOriginal => ({ ...await importOriginal<object>(), api: fakeApi, uploadBatch: batch }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
function view(readOnly = false) {
  fakeApi.mockImplementation(async path => path === "/evidence/formats" ? { formats: [{ mime_type: "image/png" }], max_files: 50, max_file_bytes: 20 * 1024 * 1024, max_batch_bytes: 100 * 1024 * 1024 } : []);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><I18nProvider><Evidence caseId="case" readOnly={readOnly} /></I18nProvider></QueryClientProvider>);
}
it("uploads every selected screenshot, resets the input and retries only failed files", async () => {
  batch.mockResolvedValueOnce({ uploaded: 1, duplicates: 0, failed: 1, results: [{ index: 0, filename: "first.png", status: "uploaded" }, { index: 1, filename: "second.png", status: "failed", error: "Invalid evidence image" }] });
  batch.mockResolvedValueOnce({ uploaded: 1, duplicates: 0, failed: 0, results: [{ index: 0, filename: "second.png", status: "uploaded" }] });
  view();
  const input = screen.getByLabelText("上传证据");
  expect(input).toHaveAttribute("multiple");
  const files = [new File(["a"], "first.png", { type: "image/png" }), new File(["b"], "second.png", { type: "image/png" })];
  fireEvent.change(input, { target: { files } });
  await screen.findByText(/second.png · 失败/);
  expect(batch).toHaveBeenNthCalledWith(1, "case", files);
  expect(input).toHaveValue("");
  fireEvent.click(screen.getByRole("button", { name: "重试失败文件" }));
  await waitFor(() => expect(batch).toHaveBeenNthCalledWith(2, "case", [files[1]]));
  await screen.findByText(/second.png · 上传成功/);
});
it("disables uploads and transcript imports for a viewer", () => {
  view(true);
  expect(screen.getByLabelText("上传证据")).toBeDisabled();
  expect(screen.getByLabelText("导入人工转录 JSON")).toBeDisabled();
  expect(screen.getByText(/不能修改证据/)).toBeInTheDocument();
});
