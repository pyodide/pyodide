import * as chai from "chai";
import { scheduleCallback } from "../../scheduler";

describe("scheduleCallback", () => {
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
            }, 11);
      });
});
