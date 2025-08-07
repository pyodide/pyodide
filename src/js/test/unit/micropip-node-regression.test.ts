/**
 * Regression test for issue #5821: Error loading micropip with pyodide version 0.28.1
 * 
 * This test ensures that when loading pyodide in Node.js without explicitly providing
 * a packageCacheDir, the package loading logic correctly falls back to CDN URLs
 * instead of trying to load from non-existent local paths.
 */
import * as chai from "chai";
import { PackageManager } from "../../load-package.ts";
import { genMockAPI, genMockModule } from "./test-helper.ts";

describe("Node.js package loading regression tests", () => {
  describe("Issue #5821: micropip loading with default config", () => {
    it("should set installBaseUrl to packageBaseUrl when packageCacheDir is undefined in Node.js", () => {
      // Mock the IN_NODE environment variable
      const originalInNode = (globalThis as any).IN_NODE;
      (globalThis as any).IN_NODE = true;

      try {
        // Create mock API with packageCacheDir undefined and packageBaseUrl set
        const mockApi = genMockAPI();
        mockApi.config.packageCacheDir = undefined;
        mockApi.config.packageBaseUrl = "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/";
        mockApi.config.cdnUrl = "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/";

        const mockMod = genMockModule();
        const pm = new PackageManager(mockApi, mockMod);

        // In Node.js with no packageCacheDir, installBaseUrl should be packageBaseUrl
        chai.assert.equal(pm.installBaseUrl, "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/");
        chai.assert.equal(pm.cdnURL, "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/");
      } finally {
        // Restore original IN_NODE value
        if (originalInNode !== undefined) {
          (globalThis as any).IN_NODE = originalInNode;
        } else {
          delete (globalThis as any).IN_NODE;
        }
      }
    });

    it("should set installBaseUrl to packageCacheDir when explicitly provided in Node.js", () => {
      // Mock the IN_NODE environment variable
      const originalInNode = (globalThis as any).IN_NODE;
      (globalThis as any).IN_NODE = true;

      try {
        // Create mock API with explicit packageCacheDir
        const mockApi = genMockAPI();
        mockApi.config.packageCacheDir = "/tmp/cache/";
        mockApi.config.packageBaseUrl = "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/";
        mockApi.config.cdnUrl = "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/";

        const mockMod = genMockModule();
        const pm = new PackageManager(mockApi, mockMod);

        // With explicit packageCacheDir, installBaseUrl should be packageCacheDir
        chai.assert.equal(pm.installBaseUrl, "/tmp/cache/");
        chai.assert.equal(pm.cdnURL, "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/");
      } finally {
        // Restore original IN_NODE value
        if (originalInNode !== undefined) {
          (globalThis as any).IN_NODE = originalInNode;
        } else {
          delete (globalThis as any).IN_NODE;
        }
      }
    });

    it("should set installBaseUrl to packageBaseUrl in browser environment", () => {
      // Mock the IN_NODE environment variable to false (browser)
      const originalInNode = (globalThis as any).IN_NODE;
      (globalThis as any).IN_NODE = false;

      try {
        const mockApi = genMockAPI();
        mockApi.config.packageCacheDir = undefined;
        mockApi.config.packageBaseUrl = "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/";

        const mockMod = genMockModule();
        const pm = new PackageManager(mockApi, mockMod);

        // In browser, installBaseUrl should always be packageBaseUrl
        chai.assert.equal(pm.installBaseUrl, "https://cdn.jsdelivr.net/pyodide/v0.28.1/full/");
        chai.assert.isUndefined(pm.cdnURL); // cdnURL is not set in browser
      } finally {
        // Restore original IN_NODE value
        if (originalInNode !== undefined) {
          (globalThis as any).IN_NODE = originalInNode;
        } else {
          delete (globalThis as any).IN_NODE;
        }
      }
    });
  });
});