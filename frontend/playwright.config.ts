import { defineConfig, devices } from "@playwright/test";

// End-to-end runs against a real API on a fixture database (jal_e2e, seeded in globalSetup) and the production build.
const E2E_DB = "postgresql+psycopg://jal:jal@localhost:5433/jal_e2e";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  use: { baseURL: "http://localhost:4173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: "uv run uvicorn app.main:app --port 8100",
      cwd: "../backend",
      env: { DATABASE_URL: E2E_DB, ADMIN_TOKEN: "e2e-admin-token" },
      url: "http://localhost:8100/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run build && npx vite preview --port 4173 --strictPort",
      env: { API_URL: "http://localhost:8100" },
      url: "http://localhost:4173",
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
