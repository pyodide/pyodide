async function main() {
    const loadPyodide = require("../dist/pyodide.js").loadPyodide;
    py = await loadPyodide({});
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
    const SegfaultHandler = require("segfault-handler");
    SegfaultHandler.registerHandler("crash1.log");
    py.setInterruptBuffer([0]);
    for (let i = 10; i < 100; i++) {
        sleep(100 * i).then(() => console.log("jsi", i));
    }
    f = py.runPython(`
    def f():
      for i in range(100_000):
        if i % 100 == 0:
          print("pyi", i)
      import pytest
    f
    `);
    py._module.shouldSuspend = true;
    await f.callSyncifying({});

    //   def f():
    //     from pyodide_js import loadPackage
    //     from js import sleep
    //     # loadPackage.syncify("micropip")
    //     sleep.syncify(1000)
    //     print(66)
    //     sleep.syncify(1000)
    //     print(66)
    //     # import pytest
    //     print(77)
    //   f
    // `);
}
main();
