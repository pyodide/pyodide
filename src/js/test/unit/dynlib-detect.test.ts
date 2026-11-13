import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  shouldLoadDynlib,
  getDynlibs,
} from "../../package-loading/dynlib-detect.ts";
import { computePythonPaths } from "../../package-loading/python-paths.ts";

const { extensionTags } = computePythonPaths([3, 14, 2]);

describe("shouldLoadDynlib", () => {
  const shouldLoad = [
    "test.so",
    "test.abi3.so",
    "test.cpython-314-wasm32-emscripten.so",
    "dir/test.cpython-314-wasm32-emscripten.so",
    "test.so.1",
    "test.so.1.2",
    "some.name.so",
  ];
  for (const path of shouldLoad) {
    it(`loads ${path}`, () => {
      assert.equal(shouldLoadDynlib(path, extensionTags), true);
    });
  }

  const shouldNotLoad = [
    "test.txt",
    "test.py",
    "test.cpython-39-x86_64-linux-gnu.so",
    "test.cpython-310-x86_64-linux-gnu.so",
    "notashared.solib",
  ];
  for (const path of shouldNotLoad) {
    it(`does not load ${path}`, () => {
      assert.equal(shouldLoadDynlib(path, extensionTags), false);
    });
  }
});

describe("getDynlibs", () => {
  it("returns resolved paths for compatible shared libraries only", () => {
    const paths = [
      "pkg/__init__.py",
      "pkg/_core.cpython-314-wasm32-emscripten.so",
      "pkg/_other.cpython-39-x86_64-linux-gnu.so",
      "pkg/libhelper.so",
    ];
    const result = getDynlibs(
      paths,
      "/lib/python3.14/site-packages",
      extensionTags,
    );
    assert.deepEqual(result, [
      "/lib/python3.14/site-packages/pkg/_core.cpython-314-wasm32-emscripten.so",
      "/lib/python3.14/site-packages/pkg/libhelper.so",
    ]);
  });

  it("normalizes . and .. segments in member paths", () => {
    const result = getDynlibs(
      ["./pkg/../pkg/mod.so"],
      "/usr/lib",
      extensionTags,
    );
    assert.deepEqual(result, ["/usr/lib/pkg/mod.so"]);
  });

  it("returns an empty array when there are no shared libraries", () => {
    const result = getDynlibs(["a.py", "b.txt"], "/usr/lib", extensionTags);
    assert.deepEqual(result, []);
  });
});
