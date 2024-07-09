import * as chai from "chai";
import abortSignalAny from "../../../common/abortSignalAny";

describe("abortSignalAny", () => {
  it("should abort the signal", () => {
    const controller = new AbortController();
    const signal = controller.signal;
    controller.abort("reason");

    const result = abortSignalAny([signal]);
    chai.assert.isTrue(result.aborted);
    chai.assert.equal(result.reason, "reason");
  });
});
