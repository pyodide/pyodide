import { expect, test } from "./fixture";

// for a persistence-related browser test see /src/tests/test_filesystem.py

test.describe("FS", () => {
  test("no directory", async ({ page }) => {
    const factory = async () => {
      const result = pyodide.runPython(
        "import os; os.path.exists('/tmp/js-test')",
      );
      return result;
    };
    const result = await page.evaluate(factory);
    expect(result).toBeFalsy();
  });
  test("has directory", async ({ page }) => {
    const factory = async () => {
      await pyodide.FS.mkdir("/tmp/js-test");
      const result = pyodide.runPython(
        "import os; os.path.exists('/tmp/js-test')",
      );
      return result;
    };
    const result = await page.evaluate(factory);
    expect(result).toBeTruthy();
  });
});

test.describe("PATH", () => {
  test("exists", async ({ page }) => {
    expect(await page.evaluate(() => pyodide.PATH)).toBeDefined();
  });
  test("has expected keys", async ({ page }) => {
    expect(
      await page.evaluate(() => typeof pyodide.PATH.dirname === "function"),
    ).toBeDefined();
    expect(
      await page.evaluate(() => typeof pyodide.PATH.normalize === "function"),
    ).toBeDefined();
  });
});

test.describe("ERRNO_CODES", () => {
  test("exists", async ({ page }) => {
    expect(await page.evaluate(() => pyodide.ERRNO_CODES)).toBeDefined();
  });
  test("has expected keys", async ({ page }) => {
    expect(await page.evaluate(() => pyodide.ERRNO_CODES.ENOENT)).toBeDefined();
    expect(await page.evaluate(() => pyodide.ERRNO_CODES.EPERM)).toBeDefined();
    expect(await page.evaluate(() => pyodide.ERRNO_CODES.EEXIST)).toBeDefined();
  });
});
