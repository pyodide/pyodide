import * as chai from "chai";
import { scheduleCallback } from "../../scheduler";

describe("scheduleCallback", () => {
  // Note: This test requires `--exit` flag to be set for mocha
  //       to avoid hanging the process
  //       see: https://github.com/facebook/react/issues/26608
  it("should call the callback immediately if timeout is 0", () => {
    const start = Date.now();
    scheduleCallback(() => {
      chai.assert.isAtMost(Date.now() - start, 4);
    });
  });

  it("should call the callback after the given timeout", () => {
    const start = Date.now();
    scheduleCallback(() => {
      chai.assert.isAtLeast(Date.now() - start, 10);
    }, 10);
  });
});
