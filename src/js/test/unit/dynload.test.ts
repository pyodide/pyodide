import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { DynlibLoader, shouldPreloadDynlib } from "../../dynload.ts";
import { genMockAPI, genMockModule } from "./test-helper.ts";

const MiB = 1024 * 1024;

describe("shouldPreloadDynlib", () => {
  it("preloads libraries at or above the threshold", () => {
    assert.ok(shouldPreloadDynlib(8 * MiB, 8 * MiB));
    assert.ok(shouldPreloadDynlib(8 * MiB + 1, 8 * MiB));
  });

  it("skips libraries below the threshold", () => {
    assert.ok(!shouldPreloadDynlib(0, 8 * MiB));
    assert.ok(!shouldPreloadDynlib(8 * MiB - 1, 8 * MiB));
  });

  it("preloads everything when the threshold is 0", () => {
    assert.ok(shouldPreloadDynlib(0, 0));
    assert.ok(shouldPreloadDynlib(1024, 0));
  });

  it("preloads nothing when the threshold is Infinity", () => {
    assert.ok(!shouldPreloadDynlib(0, Infinity));
    assert.ok(!shouldPreloadDynlib(Number.MAX_SAFE_INTEGER, Infinity));
  });
});

describe("DynlibLoader.preloadDynlibs", () => {
  const sizes: Record<string, number> = {
    "/small.so": 1024,
    "/large.so": 16 * MiB,
  };

  async function preloaded(threshold: number) {
    // @ts-ignore
    globalThis.DEBUG = false;
    const mockApi = genMockAPI({ sharedLibraryPreloadThreshold: threshold });
    const mockMod = genMockModule();
    mockMod.FS.stat = ((path: string) => ({
      size: sizes[path],
    })) as unknown as typeof mockMod.FS.stat;
    const loader = new DynlibLoader(mockApi, mockMod);
    const loaded: string[] = [];
    loader.loadDynlib = async (path: string) => {
      loaded.push(path);
    };
    await loader.preloadDynlibs(Object.keys(sizes));
    return loaded;
  }

  it("only preloads large libraries by default", async () => {
    assert.deepEqual(await preloaded(8 * MiB), ["/large.so"]);
  });

  it("preloads every library when the threshold is 0", async () => {
    assert.deepEqual(await preloaded(0), ["/small.so", "/large.so"]);
  });

  it("preloads no library when the threshold is Infinity", async () => {
    assert.deepEqual(await preloaded(Infinity), []);
  });
});
