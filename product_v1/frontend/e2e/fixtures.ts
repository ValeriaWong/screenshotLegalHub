import fs from "node:fs";
import path from "node:path";
import { test as base, expect } from "@playwright/test";
export const test = base.extend<{ authenticated: void }>({
  authenticated: [async ({ page, request }, use) => {
    const credentials = { username: "e2eadmin", password: "e2e-synthetic-password-123" };
    const status = await (await request.get("/v1/auth/status")).json();
    if (!status.initialized) {
      expect((await request.post("/v1/auth/setup", { data: { ...credentials, display_name: "E2E administrator" } })).ok()).toBeTruthy();
    } else {
      expect((await request.post("/v1/auth/login", { data: credentials })).ok()).toBeTruthy();
    }
    expect((await page.context().request.post("/v1/auth/login", { data: credentials })).ok()).toBeTruthy();
    await use();
  }, { auto: true }],
});
export { expect };

export function artifactPath(name: string) { const directory = path.resolve(process.env.E2E_REPORT_DIR || "../.tools/e2e-artifacts/" + path.basename(process.env.E2E_DATA_DIR || "manual")); fs.mkdirSync(directory, { recursive: true }); return path.join(directory, name); }
