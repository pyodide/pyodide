import assert from "assert";

describe("fileSystem", () => {
  const exists = () => {
    return pyodide.runPython("import os; os.path.exists('/tmp/js-test')");
  };
  it("no dir", async () => assert.strictEqual(exists(), false));
  it("mkdir", async () => pyodide.FS.mkdir("/tmp/js-test"));
  it("made dir", async () => assert.strictEqual(exists(), true));
});
