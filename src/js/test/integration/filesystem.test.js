const chai = require("chai");

// for a persistence-related browser test see /src/tests/test_filesystem.py

describe("FS", () => {
  it("no directory", async () => {
    const factory = async () => {
      const result = pyodide.runPython(
        "import os; os.path.exists('/tmp/js-test')"
      );
      return result;
    };
    const result = await chai.assert.isFulfilled(page.evaluate(factory));
    chai.assert.isFalse(result);
  });
  it("has directory", async () => {
    const factory = async () => {
      pyodide.FS.mkdir("/tmp/js-test");
      const result = pyodide.runPython(
        "import os; os.path.exists('/tmp/js-test')"
      );
      return result;
    };
    const result = await chai.assert.isFulfilled(page.evaluate(factory));
    chai.assert.isTrue(result);
  });
});
