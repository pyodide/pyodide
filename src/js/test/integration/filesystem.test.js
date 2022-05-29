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

describe("PATH", () => {
  it("exists", async () => {
    chai.assert.exists(pyodide.PATH);
  });
  it("has expected keys", async () => {
    chai.assert.exists(pyodide.PATH.dirname);
    chai.assert.exists(pyodide.PATH.normalize);
  });
});

describe("ERRNO_CODES", () => {
  it("exists", async () => {
    chai.assert.exists(pyodide.ERRNO_CODES);
  });
  it("has expected keys", async () => {
    chai.assert.exists(pyodide.ERRNO_CODES.ENOENT);
    chai.assert.exists(pyodide.ERRNO_CODES.EPERM);
    chai.assert.exists(pyodide.ERRNO_CODES.EEXIST);
  });
});
