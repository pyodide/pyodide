import assert from "assert";
import { loadPyodide } from "../pyodide.js";

describe("fileSystem", () => {
  let pyodide;
  it("loadPyodide", async () => {
    pyodide = await loadPyodide({ indexURL: "../../build/" });
  });
  const exists = () => {
    return pyodide.runPython("import os; os.path.exists('/tmp/js-test')");
  };
  it("no dir", async () => assert.equal(exists(), false));
  it("mkdir", async () => pyodide.fileSystem.mkdir("/tmp/js-test"));
  it("made dir", async () => assert.equal(exists(), true));
});
