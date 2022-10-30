async function main() {
    const loadPyodide = require("../dist/pyodide.js").loadPyodide;
    py = await loadPyodide();
    // let s = new WebAssembly.Suspender();
    function sleep(ms) {
        return new Promise((res) => {
            setTimeout(() => {
                console.log("sleep is resolved", ms);
                res();
            }, ms);
        });
    }
    globalThis.sleep = sleep;
    await py.loadPackage("pytest");
    py.runPython("import _pytest");
    f = py.runPython(`
    def f():
      from pyodide_js import loadPackage
      from js import sleep
      # loadPackage.syncify("micropip")
      sleep.syncify(1000)
      print(66)
      sleep.syncify(1000)
      print(66)
      import pytest
      print(77)
    f
  `);

    await f.callSyncifying({});
}
main();
