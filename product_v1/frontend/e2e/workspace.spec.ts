import { test, expect } from "./fixtures";
import AxeBuilder from "@axe-core/playwright";
test("demo → citation → bbox → review → run → gate → SSE → reload", async ({
  page,
}) => {
  await page.goto("/console.html");
  await page.getByRole("button", { name: "打开合成演示" }).click();
  await expect(page.locator(".eyebrow")).toHaveText(
    "张三与李四 · 合成借贷演示",
  );
  await page.getByRole("button", { name: /证明矩阵/ }).click();
  await page
    .getByRole("button", { name: "查看引用 1", exact: true })
    .first()
    .click();
  await expect(page.getByTestId("source-bbox")).toBeVisible();
  await expect(page.getByRole("complementary").getByRole("img")).toBeVisible();
  await page.getByRole("button", { name: /人工审核/ }).click();
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await expect(page.getByText("已保存审核")).toBeVisible();
  await page.getByRole("button", { name: /运行详情/ }).click();
  await page.getByRole("button", { name: "运行分析", exact: true }).click();
  await expect(page.getByTestId("run-status")).toHaveText("WAITING_REVIEW");
  await page.getByRole("button", { name: "批准并继续" }).click();
  await expect(page.getByTestId("run-status")).toHaveText("COMPLETED");
  await page.reload();
  await expect(page.getByTestId("run-status")).toHaveText("COMPLETED");
  await expect(page.getByTestId("sse-state")).toContainText("state-snapshot");
  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Advanced", exact: true }),
  ).toBeVisible();
  const report = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(
    report.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious",
    ),
  ).toEqual([]);
  await page.screenshot({
    path: "../artifacts/workspace-desktop.png",
    fullPage: true,
  });
});
test("mobile and reduced motion", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/console.html");
  await expect(page.locator("[data-reduced-motion=true]")).toBeVisible();
  await page.getByRole("button", { name: /时间线/ }).click();
  await expect(
    page.getByRole("heading", { name: "时间线", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../artifacts/workspace-mobile.png",
    fullPage: true,
  });
});
