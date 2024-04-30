import chai from "chai";
import * as pyodideModule from "../../emscriptenSettings";

describe("Module", () => {
  describe("noWasmDecoding", () => {
    it("should be false ", () => {
      const settings = pyodideModule.createSettings({
        indexURL: "a",
        _node_mounts: [],
        args: [],
        env: {},
        lockFileURL: "a",
        packageCacheDir: "b",
        packages: [],
      });
      chai.assert.equal(settings.noWasmDecoding, false);
    });
  });
});
