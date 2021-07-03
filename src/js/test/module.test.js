import assert from "assert";
import { Module } from "../module.js";

describe("Module", function () {
  describe("noWasmDecoding", function () {
    it("should be false ", function () {
      assert.equal(Module.noWasmDecoding, false);
    });
  });
});
