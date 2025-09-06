import { describe, it, beforeEach, afterEach } from "mocha";
import { expect } from "chai";
import { loadPyodide } from "../../pyodide";

describe("loadPyodide runtime override", () => {
  let originalDeno: any;
  let originalBun: any;
  let originalProcess: any;

  beforeEach(() => {
    // Store original globalThis values
    originalDeno = globalThis.Deno;
    originalBun = globalThis.Bun;
    originalProcess = globalThis.process;
  });

  afterEach(() => {
    // Restore original globalThis values
    globalThis.Deno = originalDeno;
    globalThis.Bun = originalBun;
    globalThis.process = originalProcess;
  });

  it("should override runtime to Node.js", async () => {
    const pyodide = await loadPyodide({ 
      runtime: 'node',
      indexURL: './'
    });

    // Test JavaScript level detection
    const jsResult = pyodide.runPython(`
import pyodide.ffi
{
    'IN_NODE': pyodide.ffi.IN_NODE,
    'IN_BROWSER': pyodide.ffi.IN_BROWSER,
    'IN_DENO': pyodide.ffi.IN_DENO,
    'IN_BUN': pyodide.ffi.IN_BUN
}
`);

    expect(jsResult.IN_NODE).to.be.true;
    expect(jsResult.IN_BROWSER).to.be.false;
    expect(jsResult.IN_DENO).to.be.false;
    expect(jsResult.IN_BUN).to.be.false;
  });

  it("should override runtime to Browser", async () => {
    const pyodide = await loadPyodide({ 
      runtime: 'browser',
      indexURL: './'
    });

    const jsResult = pyodide.runPython(`
import pyodide.ffi
{
    'IN_NODE': pyodide.ffi.IN_NODE,
    'IN_BROWSER': pyodide.ffi.IN_BROWSER,
    'IN_DENO': pyodide.ffi.IN_DENO,
    'IN_BUN': pyodide.ffi.IN_BUN
}
`);

    expect(jsResult.IN_NODE).to.be.false;
    expect(jsResult.IN_BROWSER).to.be.true;
    expect(jsResult.IN_DENO).to.be.false;
    expect(jsResult.IN_BUN).to.be.false;
  });

  it("should override runtime to Deno", async () => {
    const pyodide = await loadPyodide({ 
      runtime: 'deno',
      indexURL: './'
    });

    const jsResult = pyodide.runPython(`
import pyodide.ffi
{
    'IN_NODE': pyodide.ffi.IN_NODE,
    'IN_BROWSER': pyodide.ffi.IN_BROWSER,
    'IN_DENO': pyodide.ffi.IN_DENO,
    'IN_BUN': pyodide.ffi.IN_BUN
}
`);

    expect(jsResult.IN_NODE).to.be.false;
    expect(jsResult.IN_BROWSER).to.be.false;
    expect(jsResult.IN_DENO).to.be.true;
    expect(jsResult.IN_BUN).to.be.false;
  });

  it("should override runtime to Bun", async () => {
    const pyodide = await loadPyodide({ 
      runtime: 'bun',
      indexURL: './'
    });

    const jsResult = pyodide.runPython(`
import pyodide.ffi
{
    'IN_NODE': pyodide.ffi.IN_NODE,
    'IN_BROWSER': pyodide.ffi.IN_BROWSER,
    'IN_DENO': pyodide.ffi.IN_DENO,
    'IN_BUN': pyodide.ffi.IN_BUN
}
`);

    expect(jsResult.IN_NODE).to.be.false;
    expect(jsResult.IN_BROWSER).to.be.false;
    expect(jsResult.IN_DENO).to.be.false;
    expect(jsResult.IN_BUN).to.be.true;
  });

  it("should provide all runtime flags in Python", async () => {
    const pyodide = await loadPyodide({ 
      runtime: 'node',
      indexURL: './'
    });

    const allFlags = pyodide.runPython(`
import pyodide.ffi
{
    'IN_NODE': pyodide.ffi.IN_NODE,
    'IN_NODE_COMMONJS': pyodide.ffi.IN_NODE_COMMONJS,
    'IN_NODE_ESM': pyodide.ffi.IN_NODE_ESM,
    'IN_BROWSER': pyodide.ffi.IN_BROWSER,
    'IN_BROWSER_MAIN_THREAD': pyodide.ffi.IN_BROWSER_MAIN_THREAD,
    'IN_BROWSER_WEB_WORKER': pyodide.ffi.IN_BROWSER_WEB_WORKER,
    'IN_DENO': pyodide.ffi.IN_DENO,
    'IN_BUN': pyodide.ffi.IN_BUN,
    'IN_SAFARI': pyodide.ffi.IN_SAFARI,
    'IN_SHELL': pyodide.ffi.IN_SHELL
}
`);

    // All flags should be boolean values
    Object.values(allFlags).forEach(value => {
      expect(value).to.be.a('boolean');
    });

    // Node.js specific flags should be true
    expect(allFlags.IN_NODE).to.be.true;
    expect(allFlags.IN_BROWSER).to.be.false;
    expect(allFlags.IN_DENO).to.be.false;
    expect(allFlags.IN_BUN).to.be.false;
  });

  it("should work without runtime override (default behavior)", async () => {
    const pyodide = await loadPyodide({ 
      indexURL: './'
    });

    const jsResult = pyodide.runPython(`
import pyodide.ffi
{
    'IN_NODE': pyodide.ffi.IN_NODE,
    'IN_BROWSER': pyodide.ffi.IN_BROWSER,
    'IN_DENO': pyodide.ffi.IN_DENO,
    'IN_BUN': pyodide.ffi.IN_BUN
}
`);

    // Should detect actual environment (likely Node.js in test environment)
    expect(jsResult.IN_NODE).to.be.a('boolean');
    expect(jsResult.IN_BROWSER).to.be.a('boolean');
    expect(jsResult.IN_DENO).to.be.a('boolean');
    expect(jsResult.IN_BUN).to.be.a('boolean');
  });
});
