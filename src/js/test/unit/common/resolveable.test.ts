import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { createResolvable } from "../../../common/resolveable";

describe("createResolvable", () => {
  it("should create a resolvable promise", () => {
    const resolvable = createResolvable();
    assert.ok(resolvable.resolve instanceof Function);
    assert.ok(resolvable.reject instanceof Function);
  });

  it("should resolve the promise", async () => {
    const resolvable = createResolvable();
    resolvable.resolve();
    await resolvable;
  });

  it("should reject the promise", async () => {
    const resolvable = createResolvable();
    resolvable.reject();
    try {
      await resolvable;
      assert.fail("Promise should have been rejected");
    } catch (e) {
      assert.equal(e, undefined);
    }
  });
});
