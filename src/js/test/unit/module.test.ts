import chai from "chai";
import * as pyodideModule from "../../module";

describe("Module", () => {
  describe("noWasmDecoding", () => {
    it("should be false ", () => {
      const Module = pyodideModule.createModule();
      chai.assert.equal(Module.noWasmDecoding, false);
    });
  });
});
