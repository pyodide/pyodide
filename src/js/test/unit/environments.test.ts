import assert from "node:assert/strict";
import { describe, it } from "node:test";

// Import the module under test
import { RUNTIME_ENV } from "../../environments";

describe("RuntimeEnv", () => {
  it("should be a singleton across multiple imports", async () => {
    // Dynamic import to test singleton behavior
    const { RUNTIME_ENV: env1 } = await import("../../environments");
    const { RUNTIME_ENV: env2 } = await import("../../environments");

    assert.strictEqual(env1, env2, "RUNTIME_ENV should be the same instance");
  });

  it("should have all required properties", () => {
    const requiredFlags = [
      "IN_NODE",
      "IN_NODE_COMMONJS",
      "IN_NODE_ESM",
      "IN_BUN",
      "IN_DENO",
      "IN_BROWSER",
      "IN_BROWSER_MAIN_THREAD",
      "IN_BROWSER_WEB_WORKER",
      "IN_SAFARI",
      "IN_SHELL",
    ];

    for (const flag of requiredFlags) {
      assert.ok(
        flag in RUNTIME_ENV,
        `RUNTIME_ENV should have ${flag} property`,
      );
      assert.strictEqual(
        typeof RUNTIME_ENV[flag],
        "boolean",
        `${flag} should be boolean`,
      );
    }
  });

  it("should detect Node.js environment in test", () => {
    // In Node.js test environment, should detect Node.js
    assert.ok(RUNTIME_ENV.IN_NODE, "Should detect Node.js environment");
    assert.ok(!RUNTIME_ENV.IN_BROWSER, "Should not detect browser in Node.js");
    assert.ok(!RUNTIME_ENV.IN_DENO, "Should not detect Deno in Node.js");
    assert.ok(!RUNTIME_ENV.IN_BUN, "Should not detect Bun in Node.js");
    assert.ok(!RUNTIME_ENV.IN_SHELL, "Should not detect Shell in Node.js");
  });

  it("should have consistent derived flags for Node.js", () => {
    if (RUNTIME_ENV.IN_NODE) {
      const isCommonJS = RUNTIME_ENV.IN_NODE_COMMONJS;
      const isESM = RUNTIME_ENV.IN_NODE_ESM;

      // Should be either CommonJS or ESM, but not both
      assert.ok(
        isCommonJS || isESM,
        "Node.js should be either CommonJS or ESM",
      );
      assert.ok(
        !(isCommonJS && isESM),
        "Node.js cannot be both CommonJS and ESM",
      );

      // Browser flags should be false in Node.js
      assert.ok(
        !RUNTIME_ENV.IN_BROWSER_MAIN_THREAD,
        "Node.js should not be browser main thread",
      );
      assert.ok(
        !RUNTIME_ENV.IN_BROWSER_WEB_WORKER,
        "Node.js should not be web worker",
      );
    }
  });

  it("should have mutually exclusive main runtime flags", () => {
    const mainRuntimes = [
      RUNTIME_ENV.IN_NODE,
      RUNTIME_ENV.IN_DENO,
      RUNTIME_ENV.IN_BUN,
      RUNTIME_ENV.IN_SHELL,
    ];

    const trueCount = mainRuntimes.filter(Boolean).length;

    if (RUNTIME_ENV.IN_BROWSER) {
      assert.strictEqual(
        trueCount,
        0,
        "Browser should be mutually exclusive with server runtimes",
      );
    } else {
      assert.strictEqual(
        trueCount,
        1,
        "Should be in exactly one server runtime",
      );
    }
  });

  it("should have consistent browser sub-flags", () => {
    if (RUNTIME_ENV.IN_BROWSER) {
      const browserSubFlags = [
        RUNTIME_ENV.IN_BROWSER_MAIN_THREAD,
        RUNTIME_ENV.IN_BROWSER_WEB_WORKER,
      ];

      const trueSubFlags = browserSubFlags.filter(Boolean).length;
      assert.ok(trueSubFlags <= 1, "Cannot be both main thread and web worker");
    } else {
      // If not in browser, browser sub-flags should be false
      assert.ok(
        !RUNTIME_ENV.IN_BROWSER_MAIN_THREAD,
        "Non-browser should not be main thread",
      );
      assert.ok(
        !RUNTIME_ENV.IN_BROWSER_WEB_WORKER,
        "Non-browser should not be web worker",
      );
    }
  });

  it("should maintain consistency across property access", () => {
    // Access the same properties multiple times to ensure consistency
    const firstAccess = {
      IN_NODE: RUNTIME_ENV.IN_NODE,
      IN_BROWSER: RUNTIME_ENV.IN_BROWSER,
      IN_DENO: RUNTIME_ENV.IN_DENO,
    };

    const secondAccess = {
      IN_NODE: RUNTIME_ENV.IN_NODE,
      IN_BROWSER: RUNTIME_ENV.IN_BROWSER,
      IN_DENO: RUNTIME_ENV.IN_DENO,
    };

    assert.deepStrictEqual(
      firstAccess,
      secondAccess,
      "Runtime flags should be consistent across accesses",
    );
  });
});
