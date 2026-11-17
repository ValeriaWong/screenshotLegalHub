import { test, expect, artifactPath } from "./fixtures";
import path from "node:path";
import { execFileSync } from "node:child_process";
import type { APIRequestContext, Page } from "@playwright/test";

function seedPipeline(count = 1) {
  const id = "benchmark.pipeline-browser-" + crypto.randomUUID();
  const script = ["import sys,copy,json;sys.path.insert(0,'backend/tests')", "from benchmark_fixtures import seed", "from screenshotlegal.research.store import Store", "from screenshotlegal.research.benchmark_import import blob", "s=Store(sys.argv[1]);d,t=seed(s,'e2eadmin',sys.argv[2])", "g=copy.deepcopy(t[0]);g.update(task_id='global',region_id=None,bbox_xyxy=None,question='Is this a conversation?');t.append(g)", "all_tasks=[]", "for i in range(int(sys.argv[3])):", " for original in t:", "  row=copy.deepcopy(original);row.update(image_name='fixture.png' if i==0 else 'fixture-'+str(i+1)+'.png',task_id=original['task_id'] if i==0 else original['task_id']+'-'+str(i+1));all_tasks.append(row)", "r=blob(s,json.dumps(all_tasks).encode());names=sorted(set(row['image_name'] for row in all_tasks));d.update(tasks=r,image_files={name:blob(s,json.dumps([row for row in all_tasks if row['image_name']==name]).encode()) for name in names},images={name:t[0]['asset'] for name in names},counts=dict(d['counts'],images=len(names),kie=len(names),vqa=3*len(names)))", "with s.tx() as db:s.put('benchmark.dataset',d,'e2eadmin',db)"].join("\n");
  execFileSync(path.resolve("../.conda/screenshotlegal-v1", process.platform === "win32" ? "python.exe" : "bin/python"), ["-X", "utf8", "-c", script, process.env.E2E_DATA_DIR!, id, String(count)], { cwd: path.resolve(".."), windowsHide: true });
  return id;
}
test.afterEach(async ({ request }) => { const rows = await (await request.get("/v1/settings/models")).json(); for (const m of rows.filter((r: { model_name: string }) => r.model_name.startsWith("pipeline-fixture-"))) await request.delete("/v1/settings/models/" + m.id); });
async function prepare(request: APIRequestContext, mode = "good", count = 1) {
  const dataset = seedPipeline(count), modelName = "pipeline-fixture-" + mode + "-" + crypto.randomUUID();
  const modelResponse = await request.post("/v1/settings/models", { data: { name: modelName, base_url: "http://127.0.0.1:19432/v1", model_name: modelName, api_key: "e2e-placeholder", supports_vision: true, allow_external_egress: true, input_token_price: 0, output_token_price: 0 } });
  expect(modelResponse.ok()).toBeTruthy(); const model = await modelResponse.json();
  const prompts = await (await request.post("/v1/evaluation/benchmark-pipelines/default-prompts", { data: {} })).json();
  return { dataset, count, model: model.id as string, modelName, kie: prompts.find((p: { family: string }) => p.family === "kie").id, vqa: prompts.find((p: { family: string }) => p.family === "vqa").id };
}
async function start(page: Page, setup: Awaited<ReturnType<typeof prepare>>, name: string) {
  await page.goto("/evaluation.html?benchmark=" + setup.dataset);
  for (let i = 0; i < setup.count; i++) await page.getByRole("checkbox", { name: "选择样本 " + (i === 0 ? "fixture.png" : "fixture-" + (i+1) + ".png"), exact: true }).check();
  await page.getByRole("button", { name: "下一步：选择模型", exact: true }).click();
  await page.getByText("规则与更多设置", { exact: true }).click();
  await page.getByLabel("流程名称", { exact: true }).fill(name);
  await page.getByRole("combobox", { name: "本轮模型", exact: true }).selectOption(setup.model);
  await page.getByRole("combobox", { name: "消息抽取规则", exact: true }).selectOption(setup.kie);
  await page.getByRole("combobox", { name: "字段问答规则", exact: true }).selectOption(setup.vqa);
  await page.getByLabel("本轮最多调用次数", { exact: true }).fill(String(4 * setup.count));
  await page.getByRole("button", { name: "预览范围与调用预算（不调用模型）", exact: true }).click();
  await expect(page.getByText(setup.count + " 张图 · " + (4 * setup.count) + " 个执行单元 · 最多 " + (4 * setup.count) + " 次调用。", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "按预览启动整条流程", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible({ timeout: 15000 });
  return new URL(page.url()).searchParams.get("pipeline")!;
}
async function ledger(request: APIRequestContext, name: string) {
  const response = await request.get("http://127.0.0.1:19432/pipeline-ledger");
  return (await response.json()).requests.filter((r: { model: string }) => r.model === name);
}

test("pipeline executes new KIE association and VQA, preserves rubric and audit navigation", async ({ page, request }) => {
  const setup = await prepare(request), id = await start(page, setup, "浏览器按图完整流程");
  await expect.poll(async () => (await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json()).pipeline.status, { timeout: 30000 }).toBe("completed");
  const report = await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json();
  expect(report.report.conserved).toBeTruthy(); expect(report.report.vqa_planned).toBe(3);
  expect(await ledger(request, setup.modelName)).toHaveLength(4);
  for (const row of await ledger(request, setup.modelName)) { expect(row.has_max_tokens).toBe(false); expect(row.input_text).not.toContain("LEGACY_PRIVATE_ANSWER"); expect(row.input_text).not.toContain('"target"'); }
  await page.getByText("评分明细与统计口径", { exact: true }).click();
  await expect(page.getByRole("table", { name: "分输入方式和字段的覆盖与质量" })).toContainText("参考区域引导问答");
  const stages = page.getByRole("table", { name: "每图每阶段执行结果" });
  await stages.getByRole("row").filter({ hasText: "整图消息抽取" }).getByRole("button", { name: "查看原图、输入与返回" }).click();
  await expect(page.getByRole("img", { name: "当前原图、参考区域和本轮预测消息框" })).toBeVisible();
  await page.getByText("真正发送给模型的任务输入", { exact: true }).click();
  await expect(page.getByText('"input_protocol": "benchmark-input.v2"', { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "关闭详情", exact: true }).click();
  await page.getByText("恢复、重试与重新评分", { exact: true }).click();
  await page.getByLabel("恢复 / 重试 / 重评原因", { exact: true }).fill("核对固定参考与分母");
  await page.getByRole("button", { name: "离线重评已保存回答（零模型调用）" }).click();
  await expect.poll(async () => (await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json()).score_sets.length).toBe(2);
  expect(await ledger(request, setup.modelName)).toHaveLength(4);
  await page.screenshot({ path: artifactPath("pipeline-results.png"), fullPage: true });
  await page.getByRole("link", { name: "操作台过程记录", exact: true }).click();
  await expect(page.getByRole("heading", { name: "过程与结果详情", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开相关页面 →", exact: true })).toHaveAttribute("href", "/evaluation.html?benchmark=1&pipeline=" + id);
});

test("pipeline keeps upstream failures in the planned denominator and global VQA continues", async ({ page, request }) => {
  const setup = await prepare(request, "bad"), id = await start(page, setup, "浏览器保留失败分母");
  await expect.poll(async () => (await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json()).pipeline.status).toBe("completed_with_issues");
  const result = await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json();
  expect(result.report.execution.blocked_upstream).toBe(2); expect(result.report.planned_units).toBe(4);
  expect(await ledger(request, setup.modelName)).toHaveLength(2);
  await expect(page.getByRole("table", { name: "每图每阶段执行结果" })).toContainText("上游未提供有效预测");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: artifactPath("pipeline-failures-mobile.png"), fullPage: true });
});

test("stopping an in-flight pipeline preserves its response and prevents downstream calls", async ({ page, request }) => {
  const setup = await prepare(request, "slow"), id = await start(page, setup, "浏览器停止按图流程");
  await expect.poll(async () => (await ledger(request, setup.modelName)).length).toBe(1);
  await page.getByRole("button", { name: "停止后续调用", exact: true }).click();
  await expect.poll(async () => (await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json()).pipeline.status).toBe("cancelled");
  await expect.poll(async () => (await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json()).report.execution.response_received || 0).toBe(1);
  expect(await ledger(request, setup.modelName)).toHaveLength(1);
  const report = await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json();
  expect(report.report.execution.cancelled).toBe(3);
});

test("pipeline configuration drafts survive refresh and changed scope invalidates preview", async ({ page, request }) => {
  const setup = await prepare(request);
  await page.goto("/evaluation.html?benchmark=" + setup.dataset);
  await page.getByRole("checkbox", { name: "选择样本 fixture.png", exact: true }).check();
  await page.getByRole("button", { name: "下一步：选择模型", exact: true }).click();
  await page.getByText("规则与更多设置", { exact: true }).click();
  await page.getByLabel("流程名称", { exact: true }).fill("保留未提交的流程名称");
  await page.getByLabel("本轮最多调用次数", { exact: true }).fill("8");
  await page.getByRole("combobox", { name: "消息抽取规则", exact: true }).selectOption(setup.kie);
  await page.getByRole("combobox", { name: "字段问答规则", exact: true }).selectOption(setup.vqa);
  await page.getByRole("button", { name: "预览范围与调用预算（不调用模型）" }).click();
  await expect(page.getByRole("button", { name: "按预览启动整条流程" })).toBeEnabled();
  await page.getByLabel("本轮最多调用次数", { exact: true }).fill("7");
  await expect(page.getByRole("button", { name: "按预览启动整条流程" })).toBeDisabled();
  await page.waitForTimeout(250); await page.reload();
  await page.getByText("规则与更多设置", { exact: true }).click();
  await expect(page.getByLabel("流程名称", { exact: true })).toHaveValue("保留未提交的流程名称");
  await expect(page.getByLabel("本轮最多调用次数", { exact: true })).toHaveValue("7");
  await page.getByRole("button", { name: "返回选择样本", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "选择样本 fixture.png", exact: true })).toBeChecked();
  expect(await ledger(request, setup.modelName)).toHaveLength(0);
});


test("three selected images form one complete run with separate sample results and advanced tasks collapsed", async ({ page, request }) => {
  const setup = await prepare(request, "good", 3), id = await start(page, setup, "三个样本完整评测");
  await expect(page.getByRole("table", { name: "KIE VQA 任务列表" })).toBeHidden();
  await expect.poll(async () => (await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json()).pipeline.status, { timeout: 60000 }).toBe("completed");
  const data = await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json();
  expect(data.pipeline.selection_unit).toBe("sample"); expect(data.report.planned_units).toBe(12); expect(data.report.vqa_planned).toBe(9);
  expect(await ledger(request, setup.modelName)).toHaveLength(12);
  const samples = page.getByRole("table", { name: "样本完整流程结果" });
  await expect(samples.getByRole("row")).toHaveCount(4);
  await expect(samples.getByText("执行已完成", { exact: true })).toHaveCount(3, { timeout: 15000 });
  await page.getByRole("button", { name: "查看 fixture-2.png 的阶段", exact: true }).click();
  const stages = page.getByRole("table", { name: "每图每阶段执行结果" });
  await expect(stages.getByRole("row")).toHaveCount(5);
  await expect(stages).not.toContainText("fixture-3.png");
  await page.getByRole("button", { name: "查看全部样本阶段", exact: true }).click();
  await expect(stages.getByRole("row")).toHaveCount(13);
  await page.screenshot({ path: artifactPath("sample-workflow-three.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: artifactPath("sample-workflow-mobile.png"), fullPage: true });
  await page.getByRole("button", { name: "新建评测", exact: true }).click();
  await page.getByRole("button", { name: "返回选择样本", exact: true }).click();
  await page.getByRole("link", { name: "核对原图与任务 →", exact: true }).nth(0).click();
  await expect(page.getByRole("button", { name: "查看所有图片任务", exact: true })).toBeVisible();
});


test("evaluation opens sample workflows by default and remembers an explicit legacy tab across reload", async ({ page, request }) => {
  const setup = await prepare(request);
  await page.goto("/evaluation.html");
  await expect(page.getByRole("heading", { name: "样本完整流程评测", exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "KIE VQA 任务列表" })).toBeHidden();
  await expect(page.getByRole("table", { name: "评测与试跑运行历史", exact: true })).toBeHidden();
  await page.getByText("全部运行历史（含旧试跑）", { exact: true }).click();
  await expect(page.getByRole("table", { name: "评测与试跑运行历史", exact: true })).toBeVisible();
  await page.goto("/evaluation.html?benchmark=" + setup.dataset);
  await page.getByRole("button", { name: "评测配置与结果", exact: true }).click();
  await expect(page.getByRole("heading", { name: "创建评测运行", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "创建评测运行", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "样本完整评测（KIE / VQA）", exact: true }).click();
  await expect(page.getByRole("heading", { name: "样本完整流程评测", exact: true })).toBeVisible();
  expect(await ledger(request, setup.modelName)).toHaveLength(0);
});


test("results open directly with a clear blocked outcome and candidate boxes are never marked as adopted", async ({ page, request }) => {
  const setup = await prepare(request, "lowiou"), id = await start(page, setup, "低IoU结果阅读");
  await expect.poll(async () => (await (await request.get("/v1/evaluation/benchmark-pipelines/" + id)).json()).pipeline.status, { timeout: 30000 }).toBe("completed_with_issues");
  await page.goto("/evaluation.html?benchmark=" + setup.dataset + "&pipeline=" + id);
  await expect(page.getByRole("heading", { name: "设置模型并确认范围", exact: true })).toBeHidden();
  const outcome = page.getByLabel("本轮结论与下一步", { exact: true });
  await expect(outcome).toContainText("2 个步骤未交付回答");
  await expect(outcome).toContainText("2 / 4");
  await expect(outcome).toBeInViewport();
  const inspect = page.getByRole("button", { name: "查看未执行原因与原图", exact: true });
  await inspect.click();
  const dialog = page.getByRole("dialog", { name: "样本阶段详情", exact: true });
  await expect(dialog).toContainText("低于本轮阈值 0.6");
  await expect(dialog.locator('rect[data-role="selected"]')).toHaveCount(0);
  await expect(dialog.locator('rect[data-role="candidate"]')).toHaveCount(1);
  await expect(dialog).toContainText("最佳候选，未被采用");
  await dialog.getByText("真正发送给模型的任务输入", { exact: true }).click();
  await expect(dialog).toContainText("本题未生成实际输入，没有发送请求");
  await page.screenshot({ path: artifactPath("pipeline-inspector-desktop.png"), fullPage: false });
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(inspect).toBeFocused();
  await page.screenshot({ path: artifactPath("pipeline-results-focused.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await inspect.click();
  expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBeTruthy();
  await page.screenshot({ path: artifactPath("pipeline-inspector-mobile.png"), fullPage: false });
  expect(await ledger(request, setup.modelName)).toHaveLength(2);
});


test("insufficient call limit shows the exact gap and explicitly adjusts and previews without starting calls", async ({ page, request }) => {
  const setup = await prepare(request, "good", 3);
  await page.goto("/evaluation.html?benchmark=" + setup.dataset);
  for (const name of ["fixture.png", "fixture-2.png", "fixture-3.png"]) await page.getByRole("checkbox", { name: "选择样本 " + name, exact: true }).check();
  await page.getByRole("button", { name: "下一步：选择模型", exact: true }).click();
  await page.getByRole("combobox", { name: "本轮模型", exact: true }).selectOption(setup.model);
  const cap = page.getByLabel("本轮最多调用次数", { exact: true });
  await expect(cap).toHaveValue("9");
  await page.getByRole("button", { name: "预览范围与调用预算（不调用模型）", exact: true }).click();
  const preview = page.getByRole("region", { name: "调用次数预览", exact: true });
  await expect(preview).toContainText("本次最多需要 12 次，当前上限 9 次，还差 3 次。");
  await expect(page.getByText("这里设置本轮允许的调用次数，与服务商账户余额无关。", { exact: false })).toBeVisible();
  const startButton = page.getByRole("button", { name: "按预览启动整条流程", exact: true });
  await expect(startButton).toBeDisabled();
  await page.screenshot({ path: artifactPath("pipeline-budget-shortfall.png"), fullPage: true });
  await page.getByRole("button", { name: "将上限设为 12 次并重新预览", exact: true }).click();
  await expect(cap).toHaveValue("12");
  await expect(preview).toContainText("范围已确认：本次最多需要 12 次，当前上限 12 次，可以启动。");
  await expect(startButton).toBeEnabled();
  expect(await ledger(request, setup.modelName)).toHaveLength(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: artifactPath("pipeline-budget-confirmed-mobile.png"), fullPage: true });
  await cap.fill("11");
  await expect(preview).toContainText("配置已变化，请重新预览");
  await expect(startButton).toBeDisabled();
  await expect(page.getByRole("button", { name: "将上限设为 12 次并重新预览", exact: true })).toBeHidden();
  await cap.evaluate(el => el.closest("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
  await expect(page.getByText("请先确认当前范围的调用次数，并完成预览后再启动。", { exact: false })).toBeVisible();
  expect((await (await request.get("/v1/evaluation/benchmark-pipelines")).json()).filter((r: { dataset_id: string }) => r.dataset_id === setup.dataset)).toHaveLength(0);
  expect(await ledger(request, setup.modelName)).toHaveLength(0);
});
