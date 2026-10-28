import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  workers: 1,
  testDir: "./tests",
  fullyParallel: true,
  timeout: 30000,
  use: { baseURL: "http://127.0.0.1:4173", trace: "off" },
  webServer: [
    {
      command: "npm run dev -- --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "node tests/start-api.mjs",
      url: "https://127.0.0.1:4176/api/health",
      ignoreHTTPSErrors: true,
      reuseExistingServer: false,
    },
    {
      command: "node tests/start-api.mjs --http",
      url: "http://127.0.0.1:4177/api/health",
      reuseExistingServer: false,
    },
  ],
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
});
