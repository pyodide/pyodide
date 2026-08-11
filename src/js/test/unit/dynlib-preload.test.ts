import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  SYNC_WASM_COMPILE_LIMIT,
  shouldPreloadDynlib,
} from "../../package-loading/dynlib-preload.ts";

describe("shouldPreloadDynlib", () => {
  it("preloads everything when preloading all", () => {
    assert.ok(shouldPreloadDynlib({ path: "/a.so", size: 0 }, true));
    assert.ok(shouldPreloadDynlib({ path: "/a.so", size: 1024 }, true));
    assert.ok(shouldPreloadDynlib({ path: "/a.so" }, true));
  });

  it("skips libraries that can be compiled synchronously later", () => {
    assert.ok(!shouldPreloadDynlib({ path: "/a.so", size: 0 }, false));
    assert.ok(
      !shouldPreloadDynlib(
        { path: "/a.so", size: SYNC_WASM_COMPILE_LIMIT - 1 },
        false,
      ),
    );
  });

  it("preloads libraries at or above the synchronous compile limit", () => {
    assert.ok(
      shouldPreloadDynlib(
        { path: "/a.so", size: SYNC_WASM_COMPILE_LIMIT },
        false,
      ),
    );
    assert.ok(
      shouldPreloadDynlib(
        { path: "/a.so", size: SYNC_WASM_COMPILE_LIMIT + 1 },
        false,
      ),
    );
  });

  it("preloads a library of unknown size", () => {
    assert.ok(shouldPreloadDynlib({ path: "/a.so" }, false));
  });
});
