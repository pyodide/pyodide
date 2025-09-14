import assert from "node:assert/strict";
import { describe, it } from "node:test";

// for a persistence-related browser test see /src/tests/test_filesystem.py

describe("FS", () => {
  it("no directory", async () => {
    const factory = async () => {
      const result = pyodide.runPython(
        "import os; os.path.exists('/tmp/js-test')",
      );
      return result;
    };
    const result = await page.evaluate(factory);
    assert.ok(!result);
  });
  it("has directory", async () => {
    const factory = async () => {
      pyodide.FS.mkdir("/tmp/js-test");
      const result = pyodide.runPython(
        "import os; os.path.exists('/tmp/js-test')",
      );
      return result;
    };
    const result = await page.evaluate(factory);
    assert.ok(result);
  });
});

describe("PATH", () => {
  it("exists", async () => {
    assert.ok(await page.evaluate(() => pyodide.PATH));
  });
  it("has expected keys", async () => {
    assert.ok(await page.evaluate(() => pyodide.PATH.dirname));
    assert.ok(await page.evaluate(() => pyodide.PATH.normalize));
  });
});

describe("ERRNO_CODES", () => {
  it("exists", async () => {
    assert.ok(await page.evaluate(() => pyodide.ERRNO_CODES));
  });
  it("has expected keys", async () => {
    assert.ok(await page.evaluate(() => pyodide.ERRNO_CODES.ENOENT));
    assert.ok(await page.evaluate(() => pyodide.ERRNO_CODES.EPERM));
    assert.ok(await page.evaluate(() => pyodide.ERRNO_CODES.EEXIST));
  });
});
