import * as chai from "chai";
import chaiAsPromised from "chai-as-promised";

chai.use(chaiAsPromised);
const assert = chai.assert;
const expect = chai.expect;

import {
  withContext,
  createContextWrapper,
} from "../../../common/contextManager";

describe("withContext", () => {
  it("synchronous execution", () => {
    // Setup tracking variables
    let setupCalled = false;
    let cleanupCalled = false;
    let callbackCalled = false;

    const result = withContext(
      () => {
        setupCalled = true;
      },
      () => {
        cleanupCalled = true;
      },
      () => {
        callbackCalled = true;
        return "test result";
      },
    );

    assert.isTrue(setupCalled);
    assert.isTrue(cleanupCalled);
    assert.isTrue(callbackCalled);
    assert.equal(result, "test result");
  });

  it("asynchronous execution", async () => {
    // Setup tracking variables
    let setupCalled = false;
    let cleanupCalled = false;
    let callbackCalled = false;

    const result = await withContext(
      () => {
        setupCalled = true;
      },
      () => {
        cleanupCalled = true;
      },
      async () => {
        callbackCalled = true;
        await new Promise((resolve) => setTimeout(resolve, 10));
        return "async result";
      },
    );

    assert.isTrue(setupCalled);
    assert.isTrue(cleanupCalled);
    assert.isTrue(callbackCalled);
    assert.equal(result, "async result");
  });

  it("cleanup is called even when callback throws", () => {
    // Setup tracking variables
    let setupCalled = false;
    let cleanupCalled = false;

    assert.throws(
      () =>
        withContext(
          () => {
            setupCalled = true;
          },
          () => {
            cleanupCalled = true;
          },
          () => {
            throw new Error("Test error");
          },
        ),
      "Test error",
    );

    assert.isTrue(setupCalled);
    assert.isTrue(cleanupCalled);
  });

  it("cleanup is called even when async callback rejects", async () => {
    // Setup tracking variables
    let setupCalled = false;
    let cleanupCalled = false;

    const promise = withContext(
      () => {
        setupCalled = true;
      },
      () => {
        cleanupCalled = true;
      },
      async () => {
        await new Promise((resolve) => setTimeout(resolve, 10));
        throw new Error("Async test error");
      },
    );

    await expect(promise).to.be.rejectedWith("Async test error");
    assert.isTrue(setupCalled);
    assert.isTrue(cleanupCalled);
  });
});

describe("createContextWrapper", () => {
  it("wrapper for sync function", () => {
    // Setup tracking variables
    let setupCalled = false;
    let cleanupCalled = false;

    function testFn(x: number, y: number) {
      return x + y;
    }

    const wrappedFn = createContextWrapper(
      () => {
        setupCalled = true;
      },
      () => {
        cleanupCalled = true;
      },
    )(testFn);

    const result = wrappedFn(5, 3);

    assert.isTrue(setupCalled);
    assert.isTrue(cleanupCalled);
    assert.equal(result, 8);
  });

  it("wrapper for async function", async () => {
    // Setup tracking variables
    let setupCalled = false;
    let cleanupCalled = false;

    async function testAsyncFn(x: number, y: number) {
      await new Promise((resolve) => setTimeout(resolve, 10));
      return x * y;
    }

    const wrappedFn = createContextWrapper(
      () => {
        setupCalled = true;
      },
      () => {
        cleanupCalled = true;
      },
    )(testAsyncFn);

    const result = await wrappedFn(4, 7);

    assert.isTrue(setupCalled);
    assert.isTrue(cleanupCalled);
    assert.equal(result, 28);
  });

  it("cleanup is called when wrapped function throws", () => {
    // Setup tracking variables
    let setupCalled = false;
    let cleanupCalled = false;

    function throwingFn() {
      throw new Error("Function error");
    }

    const wrappedFn = createContextWrapper(
      () => {
        setupCalled = true;
      },
      () => {
        cleanupCalled = true;
      },
    )(throwingFn);

    assert.throws(() => wrappedFn(), "Function error");
    assert.isTrue(setupCalled);
    assert.isTrue(cleanupCalled);
  });

  it("cleanup is called when async wrapped function rejects", async () => {
    // Setup tracking variables
    let setupCalled = false;
    let cleanupCalled = false;

    async function throwingAsyncFn() {
      await new Promise((resolve) => setTimeout(resolve, 10));
      throw new Error("Async function error");
    }

    const wrappedFn = createContextWrapper(
      () => {
        setupCalled = true;
      },
      () => {
        cleanupCalled = true;
      },
    )(throwingAsyncFn);

    await assert.isRejected(wrappedFn(), "Async function error");
    assert.isTrue(setupCalled);
    assert.isTrue(cleanupCalled);
  });
});
