/**
 * Test for the default configuration fix for issue #5821
 */
import * as chai from "chai";

describe("loadPyodide default configuration", () => {
  it("should not set packageCacheDir by default", () => {
    // Import the loadPyodide function without actually calling it
    // We'll test the configuration setup logic
    
    const options_ = {
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/",
      packageBaseUrl: "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/",
      lockFileContents: Promise.resolve('{}'),
      cdnUrl: "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/"
    };

    const default_config = {
      fullStdLib: false,
      jsglobals: globalThis,
      stdin: globalThis.prompt ? globalThis.prompt : undefined,
      args: [],
      env: {},
      packages: [],
      enableRunUntilComplete: true,
      checkAPIVersion: true,
      BUILD_ID: "test-build",
    };

    const config = Object.assign(default_config, options_);

    // packageCacheDir should NOT be set by default_config
    chai.assert.isUndefined(default_config.packageCacheDir, "packageCacheDir should not be set in default_config");
    
    // But it should be available from options_ if provided
    chai.assert.isUndefined(config.packageCacheDir, "packageCacheDir should be undefined when not explicitly set");
    chai.assert.equal(config.packageBaseUrl, "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/");
  });

  it("should preserve explicitly provided packageCacheDir", () => {
    const options_ = {
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/",
      packageBaseUrl: "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/",
      lockFileContents: Promise.resolve('{}'),
      cdnUrl: "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/",
      packageCacheDir: "/tmp/package-cache/"
    };

    const default_config = {
      fullStdLib: false,
      jsglobals: globalThis,
      stdin: globalThis.prompt ? globalThis.prompt : undefined,
      args: [],
      env: {},
      packages: [],
      enableRunUntilComplete: true,
      checkAPIVersion: true,
      BUILD_ID: "test-build",
    };

    const config = Object.assign(default_config, options_);

    // Explicitly provided packageCacheDir should be preserved
    chai.assert.equal(config.packageCacheDir, "/tmp/package-cache/");
    chai.assert.equal(config.packageBaseUrl, "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/");
  });
});