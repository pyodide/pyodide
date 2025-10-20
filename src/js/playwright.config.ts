import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
const NODE = process.env.TEST_NODE;

const nodeConfig = {
  testDir: "test/integration",
  fullyParallel: true,
};

const browserConfig = {
  ...nodeConfig,
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
  ],
};

export default defineConfig({
  ...(NODE ? nodeConfig : browserConfig),
});
