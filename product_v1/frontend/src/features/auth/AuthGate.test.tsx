import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthGate } from "./AuthGate";
import { ApiError } from "../../api/client";
import { I18nProvider } from "../../i18n";
const { fakeApi } = vi.hoisted(() => ({ fakeApi: vi.fn() }));
vi.mock("../../api/client", async importOriginal => ({ ...await importOriginal<object>(), api: fakeApi }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it("keeps case content hidden until a successful login", async () => {
  let loggedIn = false;
  const user = { id: "alice", username: "alice", display_name: "Alice", role: "member", organization: "", enabled: true };
  fakeApi.mockImplementation(async path => {
    if (path === "/auth/status") return { initialized: true };
    if (path === "/auth/login") { loggedIn = true; return user; }
    if (!loggedIn) throw new ApiError("Login required", 401);
    return user;
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><I18nProvider><AuthGate><p>Private cases</p></AuthGate></I18nProvider></QueryClientProvider>);
  await screen.findByRole("button", { name: "登录" });
  expect(screen.queryByText("Private cases")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "alice" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "synthetic-password" } });
  fireEvent.click(screen.getByRole("button", { name: "登录" }));
  await screen.findByText("Private cases");
});
