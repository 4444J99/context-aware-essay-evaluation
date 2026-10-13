import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", fullyParallel: false, workers: 1, retries: 0,
  timeout: 30000, globalTimeout: 120000,
  use: { browserName: "chromium", trace: "retain-on-failure" },
  projects: [
    { name: "local-preview", testMatch: "intake.spec.ts", use: { baseURL: "http://127.0.0.1:8766" } },
    { name: "protected-contract", testMatch: "protected.spec.ts", use: { baseURL: "http://127.0.0.1:8767" } },
  ],
  webServer: [
    { command: "npm start", url: "http://127.0.0.1:8766", reuseExistingServer: false, timeout: 30000, env: { EDU_BACKEND_ORIGIN: "" } },
    { command: "npx next start --hostname 127.0.0.1 --port 8767", url: "http://127.0.0.1:8767", reuseExistingServer: false, timeout: 30000, env: { EDU_BACKEND_ORIGIN: "https://127.0.0.1:9876" } },
  ],
});
