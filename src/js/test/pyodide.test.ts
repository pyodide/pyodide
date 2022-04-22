import assert from "assert";
import fetch from "node-fetch";

describe("Pyodide", () => {
  it("runPython", async () => {
    let res = pyodide.runPython("1+1");
    assert.equal(res, 2);
  });
  it("loadPackage", async () => {
    await pyodide.loadPackage(["micropip"]);
  });
  describe("micropip", () => {
    const globalFetch = globalThis.fetch;
    before(() => {
      (globalThis as any).fetch = fetch;
    });
    after(() => {
      globalThis.fetch = globalFetch;
    });
    it("install", async () => {
      // TODO: micropip currently requires a globally defined fetch function
      await pyodide.runPythonAsync(
        'import micropip; await micropip.install("snowballstemmer")'
      );
      let res = pyodide.runPython(`
        import snowballstemmer
        len(snowballstemmer.stemmer('english').stemWords(['A', 'node', 'test']))
      `);
      assert.equal(res, 3);
    });
  });
});
