import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", fullyParallel: false, workers: 1, retries: 0,
  timeout: 30000, globalTimeout: 90000,
  use: { baseURL: "http://127.0.0.1:8766", browserName: "chromium", trace: "retain-on-failure" },
  webServer: { command: "npm start", url: "http://127.0.0.1:8766", reuseExistingServer: false, timeout: 30000, env: { EDU_BACKEND_ORIGIN: "" } }
});
