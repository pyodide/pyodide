import assert from "node:assert/strict";
import { describe, it } from "node:test";
import abortSignalAny from "../../../common/abortSignalAny";

describe("abortSignalAny", () => {
  it("should abort the signal", () => {
    const controller = new AbortController();
    const signal = controller.signal;
    controller.abort("reason");

    const result = abortSignalAny([signal]);
    assert.ok(result.aborted);
    assert.equal(result.reason, "reason");
  });
});
