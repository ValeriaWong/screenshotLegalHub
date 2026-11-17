import { test, expect, artifactPath } from "./fixtures";
for (const width of [1440, 390]) {
  test("case method experiment can preview, run and compare at " + width, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 1000 });
    const cid = (await (await request.post("/v1/cases", { data: { title: "方法试跑 " + width, description: "Synthetic browser fixture" } })).json()).id;
    const doc = await (await request.post("/v1/cases/" + cid + "/documents", { multipart: { file: { name: "原文.txt", mimeType: "text/plain", buffer: Buffer.from("甲：收到520元。乙：金额待核对。") } } })).json();
    expect((await request.post("/v1/cases/" + cid + "/documents/" + doc.id + "/parse-next", { data: { pages: 3 } })).ok()).toBeTruthy();
    await page.route("**/v1/settings/models", route => route.fulfill({ json: [{ id: "display-only", name: "模型参数界面夹具", model_name: "ui-only", base_url: "https://www.aiping.cn/api/v1", allow_external_egress: true }] }));
    await page.goto("/evaluation.html?view=agents&case=" + cid);
    await page.getByRole("combobox", { name: "分析模型", exact: true }).selectOption("display-only");
    await page.getByRole("combobox", { name: "思考模式", exact: true }).selectOption("off");
    await page.getByLabel("单次输出 token 上限", { exact: true }).fill("4000");
    await expect(page.getByRole("combobox", { name: "思考模式", exact: true })).toHaveValue("off");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
    await page.screenshot({ path: artifactPath("agent-inference-controls-" + width + ".png"), fullPage: true });
    await page.getByRole("combobox", { name: "分析模型", exact: true }).selectOption("demo");
    await expect(page.getByRole("combobox", { name: "思考模式", exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "案件方法对照与论文实验" })).toBeVisible();
    await page.getByLabel("原文.txt · 解析完成").check();
    await page.getByRole("button", { name: "检查输入与预算" }).click();
    await expect(page.getByRole("button", { name: "启动离线演练" })).toBeVisible();
    await page.screenshot({ path: artifactPath("agent-experiments-" + width + ".png") });
    await page.getByRole("button", { name: "启动离线演练" }).click();
    await expect(page.getByText("实验已加入队列，结果会自动刷新。")).toBeVisible();
    await expect(page.getByRole("link", { name: "导出论文实验原始记录（含完整输入提示与响应）" })).toBeVisible();
    await expect(page.getByText("离线流程演练，未评估法律正确性。", { exact: true })).toBeVisible({ timeout: 15000 });
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "导出论文实验原始记录（含完整输入提示与响应）" }).click()]);
    expect(download.suggestedFilename()).toMatch(/^e00_single_shot\.agentrun\..+\.json$/);
    await page.getByRole("button", { name: "检查所选对照（2）" }).click();
    await expect(page.getByLabel("对照条件")).toContainText("固定因素一致");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
  });
}
