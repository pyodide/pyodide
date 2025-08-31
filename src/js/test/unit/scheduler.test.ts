import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { scheduleCallback } from "../../scheduler";

describe("scheduleCallback", () => {
  it("should call the callback immediately if timeout is 0", () => {
    const start = Date.now();
    scheduleCallback(() => {
      assert.ok(Date.now() - start <= 4);
    });
  });

  it("should call the callback after the given timeout", () => {
    const start = Date.now();
    scheduleCallback(() => {
      assert.ok(Date.now() - start >= 10);
    }, 11);
  });
});
