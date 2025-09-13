import { describe, it, beforeEach, afterEach } from "mocha";
import { expect } from "chai";
import {
  overrideRuntime,
  detectEnvironment,
  RUNTIME_ENV,
} from "../../environments";

describe("Runtime Environment Detection", () => {
  let originalDeno: any;
  let originalBun: any;
  let originalProcess: any;
  let originalWindow: any;
  let originalDocument: any;
  let originalSelf: any;
  let originalNavigator: any;

  beforeEach(() => {
    // Store original globalThis values
    originalDeno = globalThis.Deno;
    originalBun = globalThis.Bun;
    originalProcess = globalThis.process;
    originalWindow = globalThis.window;
    originalDocument = globalThis.document;
    originalSelf = globalThis.self;
    originalNavigator = globalThis.navigator;
  });

  afterEach(() => {
    // Restore original globalThis values
    globalThis.Deno = originalDeno;
    globalThis.Bun = originalBun;
    globalThis.process = originalProcess;
    globalThis.window = originalWindow;
    globalThis.document = originalDocument;
    globalThis.self = originalSelf;
    globalThis.navigator = originalNavigator;
  });

  describe("overrideRuntime", () => {
    it("should override to Node.js environment", () => {
      overrideRuntime("node");

      const env = detectEnvironment();
      expect(env.IN_NODE).to.be.true;
      expect(env.IN_BROWSER).to.be.false;
      expect(env.IN_DENO).to.be.false;
      expect(env.IN_BUN).to.be.false;
    });

    it("should override to Browser environment", () => {
      // Mock browser environment
      (globalThis as any).window = {
        document: {
          createElement: () => ({})
        },
        sessionStorage: {}
      };
      (globalThis as any).document = (globalThis as any).window.document;
      (globalThis as any).self = (globalThis as any).window;
      (globalThis as any).navigator = {
        userAgent: "Mozilla/5.0 (compatible; Test Browser)"
      };

      overrideRuntime("browser");

      const env = detectEnvironment();
      expect(env.IN_NODE).to.be.false;
      expect(env.IN_BROWSER).to.be.true;
      expect(env.IN_DENO).to.be.false;
      expect(env.IN_BUN).to.be.false;
      expect(env.IN_BROWSER_MAIN_THREAD).to.be.true;
      expect(env.IN_BROWSER_WEB_WORKER).to.be.false;
    });

    it("should override to Deno environment", () => {
      overrideRuntime("deno");

      const env = detectEnvironment();
      expect(env.IN_NODE).to.be.false;
      expect(env.IN_BROWSER).to.be.false;
      expect(env.IN_DENO).to.be.true;
      expect(env.IN_BUN).to.be.false;
    });

    it("should override to Bun environment", () => {
      overrideRuntime("bun");

      const env = detectEnvironment();
      expect(env.IN_NODE).to.be.false;
      expect(env.IN_BROWSER).to.be.false;
      expect(env.IN_DENO).to.be.false;
      expect(env.IN_BUN).to.be.true;
    });

    it("should handle Node.js CommonJS vs ESM detection", () => {
      // Mock CommonJS environment
      overrideRuntime("node");

      // Simulate CommonJS environment
      (globalThis as any).module = { exports: {} };
      (globalThis as any).require = () => {};
      (globalThis as any).__dirname = "/test";

      overrideRuntime("node"); // Re-detect with CommonJS globals

      const env = detectEnvironment();
      expect(env.IN_NODE).to.be.true;
      expect(env.IN_NODE_COMMONJS).to.be.true;
      expect(env.IN_NODE_ESM).to.be.false;
    });

    it("should handle Browser Main Thread vs Web Worker detection", () => {
      // Mock main thread environment
      (globalThis as any).window = {
        document: {
          createElement: () => ({})
        },
        sessionStorage: {}
      };
      (globalThis as any).document = (globalThis as any).window.document;
      (globalThis as any).self = (globalThis as any).window;

      overrideRuntime("browser");

      const env = detectEnvironment();
      expect(env.IN_BROWSER).to.be.true;
      expect(env.IN_BROWSER_MAIN_THREAD).to.be.true;
      expect(env.IN_BROWSER_WEB_WORKER).to.be.false;
    });
  });

  describe("RUNTIME_ENV singleton", () => {
    it("should maintain consistency across multiple calls", () => {
      overrideRuntime("node");

      const env1 = detectEnvironment();
      const env2 = detectEnvironment();

      expect(env1).to.deep.equal(env2);
    });

    it("should update all exported constants", () => {
      overrideRuntime("node");

      expect(RUNTIME_ENV.IN_NODE).to.be.true;
      expect(RUNTIME_ENV.IN_BROWSER).to.be.false;
      expect(RUNTIME_ENV.IN_DENO).to.be.false;
      expect(RUNTIME_ENV.IN_BUN).to.be.false;
    });

    it("should update browser constants correctly", () => {
      // Mock browser environment
      (globalThis as any).window = {
        document: {
          createElement: () => ({})
        },
        sessionStorage: {}
      };
      (globalThis as any).document = (globalThis as any).window.document;
      (globalThis as any).self = (globalThis as any).window;

      overrideRuntime("browser");

      expect(RUNTIME_ENV.IN_NODE).to.be.false;
      expect(RUNTIME_ENV.IN_BROWSER).to.be.true;
      expect(RUNTIME_ENV.IN_DENO).to.be.false;
      expect(RUNTIME_ENV.IN_BUN).to.be.false;
      expect(RUNTIME_ENV.IN_BROWSER_MAIN_THREAD).to.be.true;
      expect(RUNTIME_ENV.IN_BROWSER_WEB_WORKER).to.be.false;
    });
  });

  describe("globalThis consistency", () => {
    it("should restore original globalThis values after override", () => {
      const originalDenoValue = globalThis.Deno;
      const originalBunValue = globalThis.Bun;
      const originalProcessValue = globalThis.process;

      overrideRuntime("node");

      // Verify override worked
      expect(globalThis.process).to.have.property("versions");

      // After override, original values should be restored
      expect(globalThis.Deno).to.equal(originalDenoValue);
      expect(globalThis.Bun).to.equal(originalBunValue);
      expect(globalThis.process).to.equal(originalProcessValue);
    });
  });

  describe("detectEnvironment", () => {
    it("should return all environment flags", () => {
      // Mock browser environment
      (globalThis as any).window = {
        document: {
          createElement: () => ({})
        },
        sessionStorage: {}
      };
      (globalThis as any).document = (globalThis as any).window.document;
      (globalThis as any).self = (globalThis as any).window;
      (globalThis as any).navigator = {
        userAgent: "Mozilla/5.0 (compatible; Test Browser)"
      };

      overrideRuntime("browser");

      const env = detectEnvironment();

      expect(env).to.have.property("IN_NODE");
      expect(env).to.have.property("IN_BROWSER");
      expect(env).to.have.property("IN_DENO");
      expect(env).to.have.property("IN_BUN");
      expect(env).to.have.property("IN_NODE_COMMONJS");
      expect(env).to.have.property("IN_NODE_ESM");
      expect(env).to.have.property("IN_BROWSER_MAIN_THREAD");
      expect(env).to.have.property("IN_BROWSER_WEB_WORKER");
      expect(env).to.have.property("IN_SAFARI");
      expect(env).to.have.property("IN_SHELL");
    });

    it("should return boolean values for all flags", () => {
      overrideRuntime("node");

      const env = detectEnvironment();

      Object.values(env).forEach((value) => {
        expect(value).to.be.a("boolean");
      });
    });
  });
});
