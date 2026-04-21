import { test as base } from "@playwright/test";
import path from "node:path";
const NODE = process.env.TEST_NODE;

async function pageInNode({}, use) {
  const root = path.resolve(__dirname, "../../../../", "dist");
  const { loadPyodide } = require(path.resolve(root, "pyodide"));
  const page = {
    title: () => Promise.resolve("pyodide"),
    goto: () => Promise.resolve(null),
    evaluate: (fn, ...args) => fn(...args),
  };
  await page.evaluate(async () => {
    globalThis.pyodide = await loadPyodide({ root });
  });
  await use(page);
}

async function pageInBrowser({ page }, use) {
  await page.goto("/test.html");
  await page.addScriptTag({
    url: "/pyodide.js",
  });
  await page.evaluate(async () => {
    globalThis.pyodide = await loadPyodide();
  });
  await use(page);
}
export const test = base.extend({
  page: NODE ? pageInNode : pageInBrowser,
});

export { expect } from "@playwright/test";
