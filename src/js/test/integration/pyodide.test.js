const chai = require("chai");
const fetch = require("node-fetch");

describe("Pyodide", () => {
  it("runPython", async () => {
    const factory = async () => {
      return pyodide.runPython("1+1");
    };
    const result = await chai.assert.isFulfilled(page.evaluate(factory));
    chai.assert.equal(result, 2);
  });
  describe("micropip", () => {
    const globalFetch = globalThis.fetch;

    before(async () => {
      const factory = async () => {
        globalThis.fetch = fetch;
        await pyodide.loadPackage(["micropip"]);
      };
      await chai.assert.isFulfilled(page.evaluate(factory));
    });
    after(async () => {
      const factory = async (globalFetch) => {
        globalThis.fetch = globalFetch || fetch;
      };
      await chai.assert.isFulfilled(page.evaluate(factory, globalFetch));
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
      const result = await chai.assert.isFulfilled(page.evaluate(factory));
      chai.assert.equal(result, 3);
    });
  });
});
