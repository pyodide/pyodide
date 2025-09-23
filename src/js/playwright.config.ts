import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: "test/integration",
  fullyParallel: true,
  webServer: {
    command: "npx http-server -p 3000",
    url: "http://localhost:3000",
    cwd: path.resolve(__dirname, "../../", "dist"),
  },
  use: {
    baseURL: "http://localhost:3000",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],
});
