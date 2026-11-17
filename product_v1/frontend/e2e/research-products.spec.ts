import { test, expect } from "./fixtures";
const id = () => crypto.randomUUID();
test("three research products: correction, prompts, generation, quality comparison and frozen evaluation", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  const created = await request.post("/v1/review/samples", { data: { dataset: "browser-test", content: {
    title: "浏览器研究样本", category: "contract", language: "zh", platform: "generic", kind: "synthetic",
    source_text: "来源：A说收到300元。", source_refs: [], tags: ["browser"], original_assets: [], metadata: { hidden: "HIDDEN_GOLD" },
    messages: [{ id: "m1", speaker: "A", text: "收到300元。", timestamp: null, source_refs: [] }],
    questions: [{ id: "q1", question: "消息中的金额？", answer: "300元", gold: false, task_type: "qa", message_ids: ["m1"] }],
  }, note: "browser import", idempotency_key: id() } });
  expect(created.ok()).toBeTruthy();
  const sample = (await created.json()).sample;
  await page.goto("/review.html?sample=" + sample.id);
  await expect(page.getByRole("heading", { name: "数据审核台", exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /派生图 r1/ })).toBeVisible();
  const editor = page.locator("section.card").filter({ has: page.getByRole("heading", { name: /图片审核/ }) });
  await expect(editor.getByText("本地草稿缓存可用", { exact: false })).toBeVisible();
  await editor.getByRole("button", { name: "编辑消息 m1 第1页", exact: true }).click();
  await page.getByRole("dialog").getByRole("textbox", { name: "消息文本", exact: true }).fill("收到400元，待核对。");
  await page.getByRole("dialog").getByRole("textbox", { name: "修改说明（可选）", exact: true }).fill("更正金额并保留待核对意见");
  await page.reload();
  await editor.getByRole("button", { name: "编辑消息 m1 第1页", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("textbox", { name: "消息文本", exact: true })).toHaveValue("收到400元，待核对。");
  await expect(editor.getByText(/已恢复草稿/)).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "保存并重新渲染", exact: true }).click();
  await expect(editor.getByRole("heading", { name: /当前 r2/ })).toBeVisible();
  await expect(page.getByRole("img", { name: /派生图 r2/ })).toBeVisible();
  await page.getByRole("button", { name: "评估规则与修改历史", exact: true }).click();
  await page.getByLabel("本轮修改意见 / 原因").fill("建立质量评估标准");
  await page.getByRole("button", { name: "保存为 v1", exact: true }).click();
  await expect(page.getByRole("button", { name: "保存为 v2", exact: true })).toBeVisible();
  await page.goto("/studio.html");
  await expect(page.getByRole("heading", { name: "合成生成台", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "生成规则与修改历史", exact: true }).click();
  await page.getByLabel("本轮修改意见 / 原因").fill("第一轮可追溯生成约束");
  await page.getByRole("button", { name: "保存为 v1", exact: true }).click();
  await expect(page.getByRole("button", { name: "保存为 v2", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "生成批次", exact: true }).click();
  await page.getByLabel("批次名称", { exact: true }).fill("浏览器生成批次");
  await page.getByRole("combobox", { name: "来源样本", exact: true }).selectOption(sample.id);
  await page.getByRole("button", { name: "开始生成待审样本", exact: true }).click();
  await expect.poll(async () => { const rows = await (await request.get("/v1/studio/batches")).json(); return rows.find((b: {name:string;package_ready:boolean}) => b.name === "浏览器生成批次")?.package_ready; }, {timeout:15000}).toBe(true);
  const batch = (await (await request.get("/v1/studio/batches")).json()).find((b: {name:string}) => b.name === "浏览器生成批次");
  await expect(page.locator('details[id="batch-' + batch.id + '"]').getByRole("link", { name: /下载样本和完整记录/ })).toBeVisible();
  const candidateId = batch.sample_ids[0];
  const exported = await request.get("/v1/studio/batches/" + batch.id + "/export");
  expect(exported.ok()).toBeTruthy();
  expect((await exported.body()).subarray(0, 2).toString()).toBe("PK");
  await page.goto("/review.html?sample=" + candidateId);
  const quality = page.locator("section.card").filter({ has: page.getByRole("heading", { name: /审核结论与修改意见/ }) });
  await quality.getByText("需要模型协助检查？", { exact: true }).click();
  await quality.getByRole("button", { name: "提交质量评估任务", exact: true }).click();
  await expect(quality.getByText("离线 Demo 仅验证流程，未评估质量", { exact: false })).toHaveCount(2); // findings + raw JSON
  await quality.getByRole("combobox", { name: "结论", exact: true }).selectOption("pass");
  await quality.getByText("可选：评分与评估方法", { exact: true }).click();
  await quality.getByLabel("总分（可留空，0–100）", { exact: true }).fill("90");
  await quality.getByLabel("你发现了什么问题").fill("人工检查完成");
  await quality.getByLabel("修改意见", { exact: true }).fill("保留未知事实");
  await quality.getByLabel("你依据什么作出判断").fill("逐条对照来源与消息");
  await quality.getByRole("checkbox", { name: /已核对上方当前图片/ }).check();
  await quality.getByRole("button", { name: "保存质量记录", exact: true }).click();
  await expect(quality.getByText(/之前的审核与模型意见（2）/)).toBeVisible();
  await page.goto("/studio.html");
  await page.getByRole("button", { name: "质量结果对比", exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: "浏览器生成批次" }).filter({ hasText: "90.00" })).toHaveCount(1);
  await page.screenshot({ path: "../artifacts/research-studio-comparison.png", fullPage: true });
  await page.goto("/review.html?sample=" + candidateId);
  await page.getByRole("button", { name: "导入与发布", exact: true }).click();
  await page.getByLabel("发布名称", { exact: true }).fill("浏览器冻结发布");
  await page.getByRole("checkbox", { name: /Demo 候选/ }).check();
  await page.getByRole("button", { name: "发布 1 条已审核样本", exact: true }).click();
  await expect(page.getByText(/浏览器冻结发布 · 1 条/)).toBeVisible();
  await page.goto("/evaluation.html?view=runs");
  await expect(page.getByRole("heading", { name: "评测台", exact: true })).toBeVisible();
  await page.getByLabel("运行名称", { exact: true }).fill("浏览器离线评测");
  await page.getByRole("button", { name: "开始评测", exact: true }).click();
  await expect(page.getByRole("heading", { name: /浏览器离线评测/ })).toContainText("完成");
  await expect(page.locator("section.card").filter({ has: page.getByRole("heading", { name: /浏览器离线评测/ }) }).getByRole("row").filter({ hasText: "离线 Demo" })).toContainText("0 / 1");
  await expect(page.locator("section.card").filter({ has: page.getByRole("heading", { name: "过程与恢复任务", exact: true }) }).locator("summary").first()).toContainText("完成");
  await page.screenshot({ path: "../artifacts/research-evaluation-desktop.png", fullPage: true });
  await page.goto("/review.html?sample=" + candidateId);
  await expect(page.getByRole("img", { name: /派生图/ })).toBeVisible();
  await page.screenshot({ path: "../artifacts/research-review-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: "../artifacts/research-review-mobile.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("offline typing recovers from IndexedDB and a concurrent revision cannot silently overwrite", async ({ page, request }) => {
  const created = await request.post("/v1/review/samples", { data: { dataset: "conflict", content: {
    title: "并发样本", messages: [{ id: "m1", text: "原文" }],
  }, note: "initial", idempotency_key: id() } });
  const saved = await created.json();
  const sid = saved.sample.id;
  await page.goto("/review.html?sample=" + sid);
  const editor = page.locator("section.card").filter({ has: page.getByRole("heading", { name: /图片审核/ }) });
  await expect(editor.getByText(/本地草稿缓存可用/)).toBeVisible();
  await page.route("**/v1/review/samples/*/draft", route => route.abort());
  await editor.getByRole("button", { name: "编辑消息 m1 第1页", exact: true }).click();
  await page.getByRole("dialog").getByRole("textbox", { name: "消息文本", exact: true }).fill("断网草稿");
  await page.getByRole("dialog").getByRole("textbox", { name: "修改说明（可选）", exact: true }).fill("断网纠错说明");
  await expect(editor.getByText(/本地草稿已缓存/)).toBeVisible();
  await expect(editor.getByText(/服务器草稿保存失败/)).toBeVisible();
  const conflict = await request.put("/v1/review/samples/" + sid, { data: { content: { ...saved.revision.content, title: "另一人的新版本" }, expected_revision: 1, note: "concurrent", idempotency_key: id() } });
  expect(conflict.ok()).toBeTruthy();
  await page.reload();
  await editor.getByText("样本字段、消息列表与题目", { exact: true }).click();
  await expect(editor.getByRole("textbox", { name: "消息文本", exact: true })).toHaveValue("断网草稿");
  await expect(editor.getByText(/草稿基于 r1，服务器已到 r2/)).toBeVisible();
  await expect(editor.getByRole("button", { name: "保存新版本并渲染" })).toBeDisabled();
  await page.screenshot({ path: "../artifacts/research-draft-conflict.png", fullPage: true });
});
