import assert from "assert";
import { loadPyodide } from "../pyodide.js";

describe("Pyodide", () => {
  it("runPython", async () => {
    let res = pyodide.runPython("1+1");
    assert.equal(res, 2);
  });
  it("loadPackage", async () => {
    await pyodide.loadPackage(["micropip"]);
  });
  it("micropip.install", async () => {
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
