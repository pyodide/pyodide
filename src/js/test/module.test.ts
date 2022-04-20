import assert from "assert";
import * as pyodideModule from "../module";

describe("Module", () => {
  describe("noWasmDecoding", () => {
    it("should be false ", () => {
      const Module = pyodideModule.createModule();
      assert.equal(Module.noWasmDecoding, false);
    });
  });
});
