import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  computePythonPaths,
  getInstallDir,
} from "../../package-loading/python-paths.ts";

describe("computePythonPaths", () => {
  it("computes site-packages for a version tuple", () => {
    const paths = computePythonPaths([3, 14, 2]);
    assert.equal(paths.prefix, "/");
    assert.equal(paths.sitePackages, "/lib/python3.14/site-packages");
    assert.equal(paths.dsoDir, "/usr/lib");
  });

  it("accepts a two-element version", () => {
    const paths = computePythonPaths([3, 14]);
    assert.equal(paths.sitePackages, "/lib/python3.14/site-packages");
  });

  it("computes extension tags by stripping .so", () => {
    const paths = computePythonPaths([3, 14, 0]);
    assert.deepEqual(paths.extensionTags, [
      ".cpython-314-wasm32-emscripten",
      ".abi3",
      "",
    ]);
  });
});

describe("getInstallDir", () => {
  const paths = computePythonPaths([3, 14, 2]);

  it("returns dsoDir for the dynlib target", () => {
    assert.equal(getInstallDir(paths, "dynlib"), "/usr/lib");
  });

  it("returns sitePackages for the site target", () => {
    assert.equal(getInstallDir(paths, "site"), "/lib/python3.14/site-packages");
  });

  it("defaults to sitePackages for undefined or unknown targets", () => {
    assert.equal(getInstallDir(paths), "/lib/python3.14/site-packages");
    assert.equal(
      getInstallDir(paths, "unknown"),
      "/lib/python3.14/site-packages",
    );
  });
});
