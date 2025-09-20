import assert from "assert/strict";
import { it, describe, before } from "node:test";

describe("Pyodide", () => {
  it("runPython", async () => {
    const factory = async () => {
      return pyodide.runPython("1+1");
    };
    const result = await page.evaluate(factory);
    assert.equal(result, 2);
  });
  describe("micropip", () => {
    before(async () => {
      const factory = async () => {
        return pyodide.loadPackage(["micropip"]);
      };
      const installedPackages = await page.evaluate(factory);
      assert.ok(installedPackages.length > 0);
      assert.ok(installedPackages.some((pkg) => pkg.name === "micropip"));
    });

    it("install", async () => {
      const factory = async () => {
        await pyodide.runPythonAsync(
          'import micropip; await micropip.install("snowballstemmer")',
        );
        return pyodide.runPython(`
          import snowballstemmer
          len(snowballstemmer.stemmer('english').stemWords(['A', 'node', 'test']))
        `);
      };
      const result = await page.evaluate(factory);
      assert.equal(result, 3);
    });
  });
});
