import { expect, test } from "./fixture";

test.describe("Pyodide", () => {
  test("runPython", async ({ page }) => {
    const factory = async () => {
      return pyodide.runPython("1+1");
    };
    const result = await page.evaluate(factory);
    expect(result).toStrictEqual(2);
  });
  test.describe("micropip", () => {
    test.beforeEach(async ({ page }) => {
      const factory = async () => {
        return pyodide.loadPackage(["micropip"]);
      };
      const installedPackages = await page.evaluate(factory);
      expect(installedPackages.length).toBeGreaterThan(0);
      expect(installedPackages.some((pkg) => pkg.name === "micropip")).toBe(
        true,
      );
    });

    test("install", async ({ page }) => {
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
      expect(result).toStrictEqual(3);
    });
  });
});
