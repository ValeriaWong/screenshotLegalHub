import { test, expect } from "./fixtures";
import fs from "node:fs";
import path from "node:path";
test("changed rerun marks review stale and preserves the earlier run", async ({
  page,
  request,
}) => {
  const created = await request.post("/v1/cases", {
    data: { title: "E2E synthetic staleness" },
  });
  expect(created.ok()).toBeTruthy();
  const c = await created.json();
  const folder = path.resolve("../fixtures/demo_private_lending");
  const fixture = JSON.parse(
    fs.readFileSync(path.join(folder, "fixture.json"), "utf8"),
  );
  const mapping: Record<string, unknown> = {};
  let firstEvidence = "";
  for (const n of [1, 2]) {
    const r = await request.post(`/v1/cases/${c.id}/evidence`, {
      multipart: {
        file: {
          name: `chat-${n}.png`,
          mimeType: "image/png",
          buffer: fs.readFileSync(path.join(folder, `chat-${n}.png`)),
        },
      },
    });
    expect(r.ok()).toBeTruthy();
    const evidence = await r.json();
    mapping[evidence.id] = fixture.messages.filter(
      (m: { page: number }) => m.page === n,
    );
    if (n === 1) firstEvidence = evidence.id;
  }
  expect(
    (
      await request.post(`/v1/cases/${c.id}/perception/runs`, {
        data: { adapter: "manual", fixtures: mapping },
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.put(`/v1/cases/${c.id}/matter-selection`, { data: {} })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`/v1/cases/${c.id}/analysis/compile`, { data: {} })
    ).ok(),
  ).toBeTruthy();
  async function run() {
    const r = await request.post(`/v1/cases/${c.id}/analysis/runs`, {
      data: {},
    });
    expect(r.ok()).toBeTruthy();
    const value = await r.json();
    expect(
      (
        await request.post(`/v1/runs/${value.id}/review-gates/compile-review`, {
          data: { action: "approve" },
        })
      ).ok(),
    ).toBeTruthy();
    await expect
      .poll(
        async () =>
          (await (await request.get(`/v1/runs/${value.id}`)).json()).run.status,
      )
      .toBe("COMPLETED");
    return value.id;
  }
  const old = await run();
  await page.goto(`/console.html?case=${c.id}&tab=review`);
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await expect(page.getByText("已保存审核")).toBeVisible();
  expect(
    (
      await request.post(`/v1/cases/${c.id}/perception/runs`, {
        data: {
          adapter: "manual",
          fixtures: {
            [firstEvidence]: [
              {
                text: "补充：向你借款，月底归还。",
                bbox: [30, 130, 690, 220],
                speaker: "李四",
                timestamp: "2024-02-02",
              },
            ],
          },
        },
      })
    ).ok(),
  ).toBeTruthy();
  await run();
  await page.reload();
  await expect(page.getByText("输出已变化，旧审核已失效")).toBeVisible();
  const oldGraph = await (
    await request.get(`/v1/cases/${c.id}/proof-graph?run_id=${old}`)
  ).json();
  expect(
    oldGraph.entities.filter((e: { kind: string }) => e.kind === "message"),
  ).toHaveLength(4);
  await page.screenshot({
    path: "../artifacts/review-stale.png",
    fullPage: true,
  });
});
