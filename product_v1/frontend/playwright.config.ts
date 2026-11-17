import { defineConfig } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
const executable = process.platform === "win32" ? "python.exe" : "bin/python";
const condaPython = path.resolve("../.conda/screenshotlegal-v1", executable);
const python = process.env.SCREENSHOTLEGAL_PYTHON || (fs.existsSync(condaPython) ? condaPython : path.resolve(process.platform === "win32" ? "../backend/.venv/Scripts/python.exe" : "../backend/.venv/bin/python"));
const backendPort = Number(process.env.E2E_BACKEND_PORT || 19430);
const frontendPort = Number(process.env.E2E_FRONTEND_PORT || 19431);
const modelPort = Number(process.env.E2E_MODEL_PORT || 19432);
process.env.E2E_MODEL_BASE_URL = `http://127.0.0.1:${modelPort}/v1`;
const testDataRoot = path.resolve("../.tools/e2e-data");
fs.mkdirSync(testDataRoot, { recursive: true });
const dataDir = process.env.E2E_DATA_DIR || fs.mkdtempSync(path.join(testDataRoot, "run-"));
process.env.E2E_DATA_DIR = dataDir;
export default defineConfig({
  testDir: "./e2e",
  testIgnore: "screenshot-review.spec.ts",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `"${python}" -m alembic -c ../backend/alembic.ini upgrade head && "${python}" -m uvicorn screenshotlegal.api.main:app --host 127.0.0.1 --port ${backendPort}`,
      env: { DATA_DIR: dataDir, ENABLE_REAL_MODEL: "false", ALLOW_EXTERNAL_EGRESS: "false", TRUSTED_ORIGINS: JSON.stringify([`http://127.0.0.1:${frontendPort}`, `http://localhost:${frontendPort}`]) },
      url: `http://127.0.0.1:${backendPort}/health`,
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      command: `npm run dev -- --port ${frontendPort}`,
      env: { SCREENSHOTLEGAL_API_URL: `http://127.0.0.1:${backendPort}` },
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
      timeout: 120000,
    },
    {
      command: `"${python}" e2e/mock_model.py`,
      env: { E2E_MODEL_PORT: String(modelPort) },
      url: `http://127.0.0.1:${modelPort}/health`,
      reuseExistingServer: false,
      timeout: 120000,
    },
  ],
});
