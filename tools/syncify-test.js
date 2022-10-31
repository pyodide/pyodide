async function main() {
    const loadPyodide = require("../dist/pyodide.js").loadPyodide;
    py = await loadPyodide({});
    function sleep(ms) {
        return new Promise((res) => setTimeout(res, ms));
    }
    globalThis.sleep = sleep;

    async function test1() {
        for (let i = 1; i < 40; i++) {
            sleep(25 * i).then(() => console.log("jsi", i));
        }
        f = py.runPython(`
      def f():
        for i in range(20_000):
          if i % 1000 == 0:
            print("pyi", i)
      f
      `);
        py.setInterruptBuffer([0]);
        await f.callSyncifying();
        py.setInterruptBuffer(undefined);
    }

    async function test2() {
        py.runPython(`
        from _pyodide._importhook import ModulePreloader
        import sys
        sys.meta_path.append(ModulePreloader())
      `);
        await py.pyodide_py.code.eval_code.callSyncifying(`
        import pytest
        print(pytest.__version__)
      `);
    }
    await test1();
    await test2();

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
