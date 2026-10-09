import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const db = path.join(root, ".e2e-runtime", "thesislens-e2e.sqlite3");
const api = "http://127.0.0.1:18765";
const app = "http://127.0.0.1:13000";
if (process.env.PRODUCT_QA_URL && process.env.PRODUCT_QA_URL !== app) {
  throw new Error("E2E refuses an external frontend URL; use the isolated Playwright server.");
}
if (process.env.PRODUCT_QA_API && process.env.PRODUCT_QA_API !== api) {
  throw new Error("E2E refuses an external API URL; use the isolated Playwright backend.");
}
if (process.env.THESISLENS_DB && path.resolve(process.env.THESISLENS_DB) !== db) {
  throw new Error("E2E refuses a personal THESISLENS_DB; the test database is fixed and isolated.");
}
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  webServer: [
    {
      command: ".\\.venv\\Scripts\\python.exe -m backend.e2e_server",
      cwd: root,
      url: `${api}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { THESISLENS_DB: db, THESISLENS_E2E_DB: db,
        THESISLENS_CACHE_DIR: path.join(root, ".e2e-runtime", "cache"),
        THESISLENS_OFFLINE: "true", ENABLE_JEV: "false" },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 13000",
      cwd: import.meta.dirname,
      url: app,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { API_URL: api },
    },
  ],
  use: {
    baseURL: app,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
});
