import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";
import { calculateInstallBaseUrl } from "../../compat";
import { PackageManager, toStringArray } from "../../load-package.ts";
import { genMockAPI, genMockModule } from "./test-helper.ts";

describe("PackageManager", () => {
  it("should initialize with API and Module", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();
    const _ = new PackageManager(mockApi, mockMod);
  });
});

describe("logStdout and logStderr", () => {
  it("Should use console.log and console.error if no logger is provided", (t) => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();

    const pm = new PackageManager(mockApi, mockMod);

    const logSpy = t.mock.method(pm, "stdout");
    const errorSpy = t.mock.method(pm, "stderr");

    pm.logStdout("stdout");
    pm.logStderr("stderr");

    assert.equal(logSpy.mock.callCount(), 1);
    assert.equal(errorSpy.mock.callCount(), 1);
    assert.equal(logSpy.mock.calls[0].arguments[0], "stdout");
    assert.equal(errorSpy.mock.calls[0].arguments[0], "stderr");
  });

  it("Should be overwritten when setCallbacks is called", (t) => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();

    const pm = new PackageManager(mockApi, mockMod);

    const stdoutLogger = t.mock.method(pm, "stdout");
    const stderrLogger = t.mock.method(pm, "stderr");

    pm.setCallbacks(
      stdoutLogger,
      stderrLogger,
    )(() => {
      pm.logStdout("stdout");
      pm.logStderr("stderr");
    })();

    assert.equal(stdoutLogger.mock.callCount(), 1);
    assert.equal(stderrLogger.mock.callCount(), 1);
    assert.equal(stdoutLogger.mock.calls[0].arguments[0], "stdout");
    assert.equal(stderrLogger.mock.calls[0].arguments[0], "stderr");
  });
});

describe("toStringArray", () => {
  it("Should convert string to array of strings", () => {
    assert.deepEqual(toStringArray("hello"), ["hello"]);
  });

  it("Should return the array if it is already an array", () => {
    assert.deepEqual(toStringArray(["hello", "world"]), ["hello", "world"]);
  });

  it("Should convert PyProxy to array of strings", () => {
    // TODO: use real PyProxy
    const pyProxyMock = {
      toJs: () => ["hello", "world"],
    };

    assert.deepEqual(toStringArray(pyProxyMock), ["hello", "world"]);
  });
});

describe("getLoadedPackageChannel", () => {
  it("Should return the loaded package from loadedPackages obj", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();

    const pm = new PackageManager(mockApi, mockMod);
    pm.loadedPackages = {
      package: "channel",
    };

    const loadedPackage = pm.getLoadedPackageChannel("package");
    assert.equal(loadedPackage, "channel");

    const notLoadedPackage = pm.getLoadedPackageChannel("notLoadedPackage");
    assert.equal(notLoadedPackage, null);
  });

  describe("streamReady and flushing buffers", () => {
    it("Should flush stdout and stderr buffers when stream is ready", (t) => {
      const mockApi = genMockAPI();
      const mockMod = genMockModule();

      const logStdoutSpy = t.mock.method(mockMod, "_print_stdout");
      const logStderrSpy = t.mock.method(mockMod, "_print_stderr");

      const pm = new PackageManager(mockApi, mockMod);
      pm.logStdout("stdout message");
      pm.logStderr("stderr message");

      // not called yet, buffers should not be flushed
      assert.equal(logStdoutSpy.mock.callCount(), 0);
      assert.equal(logStderrSpy.mock.callCount(), 0);

      pm.flushBuffers();

      // now buffers should be flushed
      assert.equal(logStdoutSpy.mock.callCount(), 1);
      assert.equal(logStderrSpy.mock.callCount(), 1);
    });
  });
});

describe("calculateInstallBaseUrl", () => {
  let originalLocation: any;

  beforeEach(() => {
    // Store original location
    originalLocation = globalThis.location;
  });

  afterEach(() => {
    // Restore original location
    if (originalLocation) {
      globalThis.location = originalLocation;
    } else {
      delete (globalThis as any).location;
    }
  });

  it("Should extract base URL from absolute HTTP URL", () => {
    const result = calculateInstallBaseUrl(
      "https://cdn.example.com/pyodide/pyodide-lock.json",
    );
    assert.equal(result, "https://cdn.example.com/pyodide/");
  });

  it("Should extract base URL from file URL", () => {
    const result = calculateInstallBaseUrl(
      "file:///tmp/pyodide/pyodide-lock.json",
    );
    assert.equal(result, "file:///tmp/pyodide/");
  });

  it("Should extract base URL from relative URL with path", () => {
    const result = calculateInstallBaseUrl("./pyodide/pyodide-lock.json");
    assert.equal(result, "./pyodide/");
  });

  it("Should extract base URL from relative URL with parent directory", () => {
    const result = calculateInstallBaseUrl("../pyodide/pyodide-lock.json");
    assert.equal(result, "../pyodide/");
  });

  it("Should handle URL with no path component", () => {
    const result = calculateInstallBaseUrl("pyodide-lock.json");
    assert.equal(result, ".");
  });

  it("Should handle empty string", () => {
    const result = calculateInstallBaseUrl("");
    assert.equal(result, ".");
  });

  it("Should fallback to location when URL has no slash", () => {
    // Mock browser location
    (globalThis as any).location = {
      toString: () => "https://example.com/app/",
    };

    const result = calculateInstallBaseUrl("pyodide-lock.json");
    assert.equal(result, "https://example.com/app/");
  });

  it("Should fallback to location when URL is empty", () => {
    // Mock browser location
    (globalThis as any).location = {
      toString: () => "https://example.com/app/",
    };

    const result = calculateInstallBaseUrl("");
    assert.equal(result, "https://example.com/app/");
  });

  it("Should fallback to '.' when no location available", () => {
    // Remove location to simulate environment without location
    delete (globalThis as any).location;

    const result = calculateInstallBaseUrl("pyodide-lock.json");
    assert.equal(result, ".");
  });

  it("Should handle URL with query parameters", () => {
    const result = calculateInstallBaseUrl(
      "https://cdn.example.com/pyodide/pyodide-lock.json?v=1.0",
    );
    assert.equal(result, "https://cdn.example.com/pyodide/");
  });

  it("Should handle URL with hash fragment", () => {
    const result = calculateInstallBaseUrl(
      "https://cdn.example.com/pyodide/pyodide-lock.json#section",
    );
    assert.equal(result, "https://cdn.example.com/pyodide/");
  });

  it("Should handle URL with both query parameters and hash", () => {
    const result = calculateInstallBaseUrl(
      "https://cdn.example.com/pyodide/pyodide-lock.json?v=1.0#section",
    );
    assert.equal(result, "https://cdn.example.com/pyodide/");
  });

  it("Should handle URL with username and password", () => {
    const result = calculateInstallBaseUrl(
      "https://user:pass@cdn.example.com/pyodide/pyodide-lock.json",
    );
    assert.equal(result, "https://user:pass@cdn.example.com/pyodide/");
  });
});
