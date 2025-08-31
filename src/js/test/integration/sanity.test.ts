import assert from "node:assert/strict";
import { it } from "node:test";

it("should pass a basic truthy sanity test (node)", async () => {
  assert.doesNotReject(Promise.resolve());
});

it("should pass a basic sanity test in browser (puppeteer)", async () => {
  const title = await page.title();
  assert.strictEqual(title, "pyodide");
});
