import assert from "assert";
import { Module } from "../module.js";

describe("Module", () => {
  describe("noWasmDecoding", () => {
    it("should be false ", () => {
      assert.equal(Module.noWasmDecoding, false);
    });
  });
});
