import { test, expect, artifactPath } from "./fixtures";
import path from "node:path";
import { execFileSync } from "node:child_process";
function seed() {
  const id = "benchmark.author-browser-" + crypto.randomUUID();
  const script = ["import sys;sys.path.insert(0,'backend/tests')", "from benchmark_fixtures import seed", "from screenshotlegal.research.store import Store", "from screenshotlegal.research.benchmark import Benchmark,DEFAULTS", "s=Store(sys.argv[1]);d,t=seed(s,'e2eadmin',sys.argv[2]);b=Benchmark(s)", "for f,m in DEFAULTS.items():", " b.save_prompt('e2eadmin',dict(name=sys.argv[2],family=f,parent_id=None,markdown=m,note='offline author browser fixture',idempotency_key=sys.argv[2]+f))", "with s.tx() as db:", " s.put('benchmark.attempt',dict(id='browser-kie.'+sys.argv[2],run_id='synthetic-fixture-only',dataset_id=sys.argv[2],task_id='kie',created_at='2026-10-29T00:00:00Z',task_family='kie.extract',status='completed',image_sha256=d['images']['fixture.png']['sha256'],fixture=True,demo=True,parsed=dict(dialog_name=None,conversation=[dict(id='0',content='explicit synthetic transport fixture',bbox=[10,10,110,90],message_bbox=[10,10,110,90],speaker='fixture',timestamp=None,transfer=None,file=None,image=None)])),'e2eadmin',db)"].join("\n");
  execFileSync(path.resolve("../.conda/screenshotlegal-v1", process.platform === "win32" ? "python.exe" : "bin/python"), ["-X", "utf8", "-B", "-c", script, process.env.E2E_DATA_DIR!, id], { cwd: path.resolve(".."), windowsHide: true });
  return id;
}
for (const method of ["E05", "E01", "E21", "E15", "E16"]) {
 test("author " + method + " runs with explicit budgets, traces and named exports", async ({ page, request }) => {
  const id = seed();
  await page.setViewportSize({ width: 1440, height: 1000 });
  test.setTimeout(300000);
  const upstream = "browser-kie." + id;
    await page.goto("/evaluation.html?benchmark=" + id);
    await page.getByRole("button", { name: "单阶段调试", exact: true }).click();
    const task = method === "E05" ? "kie" : "vqa";
    await page.getByRole("checkbox", { name: "选择任务 " + task, exact: true }).check();
    await page.getByRole("combobox", { name: "答题方法", exact: true }).selectOption(method);
    const start = page.getByRole("button", { name: "开始所选任务", exact: true });
    await expect(start).toBeDisabled();
    await page.getByRole("spinbutton", { name: "本次最多调用次数", exact: true }).fill(method === "E05" ? "4" : method === "E21" ? "5" : "14");
    await page.getByRole("textbox", { name: "本次运行名称", exact: true }).fill("作者控制器离线界面检查 " + method);
    if (["E01", "E21"].includes(method)) await page.getByRole("combobox", { name: "模型看什么", exact: true }).selectOption("vqa_image_full");
    if (["E15", "E16"].includes(method)) {
      await page.getByRole("combobox", { name: "模型看什么", exact: true }).selectOption("vqa_predicted_text");
      await page.getByRole("textbox", { name: "上游 KIE 结果编号", exact: true }).fill(upstream);
    }
    const started = page.waitForResponse(r => r.url().endsWith("/v1/evaluation/benchmark-runs") && r.request().method() === "POST");
    await start.click();
    const response = await started; expect(response.ok()).toBeTruthy(); const run = await response.json();
    await expect.poll(async () => {
      const response = await request.get("/v1/evaluation/benchmark-runs/" + run.id);
      expect(response.ok(), method + ": " + await response.text()).toBeTruthy();
      return (await response.json()).run?.status;
    }, { timeout: 180000 }).toBe("completed");
    const record = await (await request.get("/v1/evaluation/benchmark-runs/" + run.id)).json();
    const steps = { E05: 4, E01: 1, E21: 2, E15: 1, E16: 4 }[method]!;
    expect(record.method_steps).toHaveLength(steps);
    expect(record.report.model_calls).toBe(0); // Explicit Demo transport; no paid or paper quality claim.
    await page.getByText("fixture.png · 执行已完成", { exact: true }).click();
    await page.getByText("查看此方法逐步输入与返回", { exact: true }).click();
    await expect(page.getByText("反馈中的自评分不代表 KIE、VQA 或法律准确率。", { exact: true })).toBeVisible();
    const download = page.waitForEvent("download"); await page.getByRole("link", { name: "导出本次完整结果", exact: true }).click();
    const file = await download; expect(file.suggestedFilename()).toContain(({ E05: "e05_self_refine.", E01: "e01_react.", E21: "e21_reflexion.", E15: "e15_raptor.", E16: "e16_lightrag." } as Record<string, string>)[method]); await file.saveAs(artifactPath(file.suggestedFilename()));
    await page.screenshot({ path: artifactPath("author-method-" + method + "-desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: artifactPath("author-method-" + method + "-mobile.png"), fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
 });
}
