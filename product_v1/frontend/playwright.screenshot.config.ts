import { defineConfig } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const condaPython = path.resolve("../.conda/screenshotlegal-v1", process.platform === "win32" ? "python.exe" : "bin/python");
const python = process.env.SCREENSHOTLEGAL_PYTHON || (fs.existsSync(condaPython) ? condaPython : path.resolve(process.platform === "win32" ? "../backend/.venv/Scripts/python.exe" : "../backend/.venv/bin/python"));
const backendPort = Number(process.env.E2E_BACKEND_PORT || 20430);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT || 20431);
const backendUrl = "http://127.0.0.1:" + backendPort;
const frontendUrl = "http://127.0.0.1:" + frontendPort;
const dataRoot = path.resolve("../.tools/screenshot-e2e-data");
fs.mkdirSync(dataRoot, { recursive: true });
const dataDir = fs.mkdtempSync(path.join(dataRoot, "run-"));
process.env.E2E_DATA_DIR = dataDir;

export default defineConfig({
  testDir: "./e2e", testMatch: "screenshot-review.spec.ts", workers: 1, timeout: 120000,
  outputDir: "../reports/screenshot-panel-2026-11-06/browser-artifacts",
  use: { baseURL: frontendUrl, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    {
      command: '"' + python + '" e2e/seed_screenshot_review.py && "' + python + '" -m uvicorn screenshotlegal.api.main:app --host 127.0.0.1 --port ' + backendPort,
      env: { DATA_DIR: dataDir, ENABLE_REAL_MODEL: "false", ALLOW_EXTERNAL_EGRESS: "false", TRUSTED_ORIGINS: JSON.stringify([frontendUrl]) },
      url: backendUrl + "/health", reuseExistingServer: false, timeout: 120000,
    },
    {
      command: '"' + process.execPath + '" node_modules/vite/bin/vite.js --host 127.0.0.1 --port ' + frontendPort,
      env: { SCREENSHOTLEGAL_API_URL: backendUrl },
      url: frontendUrl, reuseExistingServer: false, timeout: 120000,
    },
  ],
});
