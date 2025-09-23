import { test as base } from "@playwright/test";

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.goto("/test.html");
    await page.addScriptTag({
      url: "/pyodide.js",
    });
    await page.evaluate(async () => {
      globalThis.pyodide = await loadPyodide();
    });
    await use(page);
  },
});

export { expect } from "@playwright/test";
