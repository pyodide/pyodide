import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { makeWarnOnce } from "../../../common/warning";

describe("makeWarnOnce", () => {
  it("should return a function", () => {
    const warn = makeWarnOnce("warning");
    assert.ok(warn instanceof Function);
  });

  it("should warn once", (t) => {
    const warn = makeWarnOnce("warning");
    const console_warn = t.mock.method(console, "warn");
    warn();
    warn();

    assert.ok(console_warn.mock.callCount() === 1);
  });
});
