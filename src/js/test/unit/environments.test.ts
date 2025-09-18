import { describe, it, beforeEach, afterEach } from "mocha";
import { expect } from "chai";
import { overrideRuntime, detectEnvironment } from "../../environments";

describe("Runtime Environment Detection", () => {
  let originalGlobals: Record<string, any>;
  beforeEach(() => {
    // Store original globalThis values
    originalGlobals = {
      Deno: (globalThis as any).Deno,
      Bun: (globalThis as any).Bun,
      process: (globalThis as any).process,
      window: (globalThis as any).window,
      document: (globalThis as any).document,
      self: (globalThis as any).self,
      navigator: (globalThis as any).navigator,
    };
  });

  afterEach(() => {
    // Restore original globalThis values
    for (const [key, value] of Object.entries(originalGlobals)) {
      try {
        // Skip navigator in Node.js as it's a getter-only property
        if (
          key === "navigator" &&
          typeof process !== "undefined" &&
          process.versions?.node
        ) {
          continue;
        }
        (globalThis as any)[key] = value;
      } catch (error) {
        // Skip properties that can't be restored (like getter-only properties)
        console.warn(`Could not restore globalThis.${key}:`, error);
      }
    }
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
          createElement: () => ({}),
        },
        sessionStorage: {},
      };
      (globalThis as any).document = (globalThis as any).window.document;
      (globalThis as any).self = (globalThis as any).window;

      // Skip navigator assignment in Node.js as it's a getter-only property
      if (typeof process === "undefined" || !process.versions?.node) {
        (globalThis as any).navigator = {
          userAgent: "Mozilla/5.0 (compatible; Test Browser)",
        };
      }

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
      expect(env.IN_NODE).to.be.true; // Deno is Node-compatible
      expect(env.IN_BROWSER).to.be.false;
      expect(env.IN_DENO).to.be.true;
      expect(env.IN_BUN).to.be.false;
    });

    it("should override to Bun environment", () => {
      overrideRuntime("bun");

      const env = detectEnvironment();
      expect(env.IN_NODE).to.be.true; // Bun is Node-compatible
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
          createElement: () => ({}),
        },
        sessionStorage: {},
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

  describe("Environment detection consistency", () => {
    it("should maintain consistency across multiple calls", () => {
      overrideRuntime("node");

      const env1 = detectEnvironment();
      const env2 = detectEnvironment();

      expect(env1).to.deep.equal(env2);
    });

    it("should update all environment flags", () => {
      overrideRuntime("node");
      const env = detectEnvironment();

      expect(env.IN_NODE).to.be.true;
      expect(env.IN_BROWSER).to.be.false;
      expect(env.IN_DENO).to.be.false;
      expect(env.IN_BUN).to.be.false;
    });

    it("should update browser flags correctly", () => {
      // Mock browser environment
      (globalThis as any).window = {
        document: {
          createElement: () => ({}),
        },
        sessionStorage: {},
      };
      (globalThis as any).document = (globalThis as any).window.document;
      (globalThis as any).self = (globalThis as any).window;

      overrideRuntime("browser");
      const env = detectEnvironment();

      expect(env.IN_NODE).to.be.false;
      expect(env.IN_BROWSER).to.be.true;
      expect(env.IN_DENO).to.be.false;
      expect(env.IN_BUN).to.be.false;
      expect(env.IN_BROWSER_MAIN_THREAD).to.be.true;
      expect(env.IN_BROWSER_WEB_WORKER).to.be.false;
    });
  });

  describe("globalThis consistency", () => {
    it("should restore original globalThis values after override", () => {
      const globals = globalThis as any;
      const originalDenoValue = globals.Deno;
      const originalBunValue = globals.Bun;
      const originalProcessValue = globals.process;

      overrideRuntime("node");

      // Verify override worked
      expect(globals.process).to.have.property("versions");

      // After override, original values should be restored
      expect(globals.Deno).to.equal(originalDenoValue);
      expect(globals.Bun).to.equal(originalBunValue);
      expect(globals.process).to.equal(originalProcessValue);
    });
  });

  describe("detectEnvironment", () => {
    it("should return all environment flags", () => {
      // Mock browser environment
      (globalThis as any).window = {
        document: {
          createElement: () => ({}),
        },
        sessionStorage: {},
      };
      (globalThis as any).document = (globalThis as any).window.document;
      (globalThis as any).self = (globalThis as any).window;

      // Skip navigator assignment in Node.js as it's a getter-only property
      if (typeof process === "undefined" || !process.versions?.node) {
        (globalThis as any).navigator = {
          userAgent: "Mozilla/5.0 (compatible; Test Browser)",
        };
      }

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
