import { test, expect } from "./fixtures";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";

test("batch screenshots → save model → connectivity failure/success → recognize → logout", async ({ page, request }) => {
  const response = await request.post("/v1/cases", { data: { title: "E2E batch screenshots" } });
  const c = await response.json();
  await page.goto(`/console.html?case=${c.id}&tab=evidence`);
  await page.getByLabel("上传证据", { exact: true }).setInputFiles([1, 2].map(i => path.resolve(`../fixtures/demo_private_lending/chat-${i}.png`)));
  await expect(page.getByRole("heading", { name: "本批上传结果" })).toBeVisible();
  await expect(page.getByText("chat-1.png · 上传成功", { exact: true })).toBeVisible();
  await expect(page.getByText("chat-2.png · 上传成功", { exact: true })).toBeVisible();
  await expect(page.locator(".thumbnail")).toHaveCount(2);
  await page.getByRole("button", { name: /模型设置/ }).click();
  await page.getByLabel("配置名称").fill("E2E vision model");
  await page.getByLabel("API 基础地址").fill(process.env.E2E_MODEL_BASE_URL!);
  await page.getByLabel("模型标识").fill("e2e-vision");
  await page.getByLabel("API Key", { exact: true }).fill("incorrect-synthetic-key");
  await page.getByLabel(/允许向该服务/).check();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await page.getByRole("button", { name: "测试文本连通性" }).click();
  await expect(page.getByRole("alert")).toContainText("连接失败");
  await page.getByRole("button", { name: "编辑模型", exact: true }).click();
  await expect(page.getByLabel("API Key", { exact: true })).toHaveValue("");
  await page.getByLabel("API Key", { exact: true }).fill("e2e-placeholder");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await page.getByRole("button", { name: "测试文本连通性" }).click();
  await expect(page.getByRole("status").filter({ hasText: "文本测试 · 连接成功" })).toBeVisible();
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(axe.violations.filter(v => ["serious", "critical"].includes(v.impact || ""))).toEqual([]);
  await page.screenshot({ path: "../artifacts/model-settings.png", fullPage: true });
  await page.getByRole("button", { name: /^02/ }).click();
  await page.getByLabel("使用已配置视觉模型").check();
  await page.getByRole("button", { name: "识别截图", exact: true }).click();
  await expect.poll(async () => (await (await request.get(`/v1/cases/${c.id}/source-refs`)).json()).length).toBe(2);
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByRole("button", { name: "登录", exact: true })).toBeVisible();
  await expect(page.getByLabel("选择案件")).toHaveCount(0);
  await page.getByLabel("用户名", { exact: true }).fill("e2eadmin");
  await page.getByLabel("密码", { exact: true }).fill("e2e-synthetic-password-123");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByLabel("选择案件")).toBeVisible();
});

test("users can be created in the UI and a shared viewer cannot upload", async ({ page, request, browser, baseURL }) => {
  await page.goto("/console.html?tab=users");
  const form = page.getByRole("heading", { name: "账号管理" }).locator("..");
  const username = `viewer${Date.now()}`;
  await form.getByLabel("用户名", { exact: true }).fill(username);
  await form.getByLabel("显示名称", { exact: true }).fill("E2E viewer");
  await form.getByLabel("密码", { exact: true }).fill("viewer-synthetic-password");
  await form.getByRole("button", { name: "添加用户", exact: true }).click();
  await expect(form.getByText(`E2E viewer (${username})`)).toBeVisible();
  const c = await (await request.post("/v1/cases", { data: { title: "E2E shared viewer case" } })).json();
  await page.goto(`/console.html?case=${c.id}&tab=overview`);
  await page.getByLabel("用户名", { exact: true }).fill(username);
  await page.getByRole("button", { name: "授权账号", exact: true }).click();
  await expect(page.getByText(`${username} · 仅查看`, { exact: true })).toBeVisible();
  const context = await browser.newContext({ baseURL });
  try {
    expect((await context.request.post("/v1/auth/login", { data: { username, password: "viewer-synthetic-password" } })).ok()).toBeTruthy();
    const viewer = await context.newPage();
    await viewer.goto(`/console.html?case=${c.id}&tab=evidence`);
    await expect(viewer.getByLabel("上传证据", { exact: true })).toBeDisabled();
    await expect(viewer.getByText(/不能修改证据/)).toBeVisible();
    expect((await context.request.get("/v1/settings/models")).ok()).toBeTruthy();
    expect(await (await context.request.get("/v1/settings/models")).json()).toEqual([]);
  } finally { await context.close(); }
});
