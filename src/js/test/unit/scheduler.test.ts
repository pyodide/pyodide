import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { scheduleCallback } from "../../scheduler";

describe("scheduleCallback", () => {
  it("should call the callback immediately if timeout is 0", (t) => {
    t.mock.timers.enable({ apis: ["setImmediate"] });

    let executed = false;
    scheduleCallback(() => {
      executed = true;
    });

    t.mock.timers.tick(1);
    assert.ok(executed);
  });

  it("should call the callback after the given timeout", (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });

    let executed = false;
    scheduleCallback(() => {
      executed = true;
    }, 11);

    t.mock.timers.tick(11);
    assert.ok(executed);
  });
});
