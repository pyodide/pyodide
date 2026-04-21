import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { createLock } from "../../../common/lock";

describe("createLock", () => {
  it("should create a lock", () => {
    const lock = createLock();
    assert.ok(lock instanceof Function);
  });

  it("should acquire the lock", async () => {
    const lock = createLock();
    const release = await lock();
    assert.ok(release instanceof Function);
  });

  it("should release the lock", async () => {
    const lock = createLock();
    const release = await lock();
    release();
  });

  it("should acquire the lock in order", async () => {
    const lock = createLock();
    let released = false;
    const release = await lock();

    setTimeout(() => {
      assert.ok(released === false);
      release();
      released = true;
    }, 100);

    assert.ok(released === false);
    const release2 = await lock();
    assert.ok(released);

    release2();
  });
});
