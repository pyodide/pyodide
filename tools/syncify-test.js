async function main() {
    const loadPyodide = require("../dist/pyodide.js").loadPyodide;
    py = await loadPyodide();
    function sleep(ms) {
        return [new Promise((res) => setTimeout(res, ms))];
    }
    globalThis.sleep = sleep;

    async function test1() {
        await py.pyodide_py.code.eval_code.callSyncifying(`
        from js import sleep
        print("a")
        from pyodide_js._module import validSuspender
        print("validSuspender.value:", validSuspender.value)
        sleep(1000)[0].syncify()
        print("b")
      `);
    }
    await test1();

    async function test2() {
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
    // await test2();

    async function test3() {
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

    globalThis.loadPackage = function(pkg){
      return [py.loadPackage(pkg)];
    }

    async function test4() {
        f = py.runPython(`
          def f():
            from js import loadPackage
            loadPackage("micropip")[0].syncify()
            import micropip
            print(micropip)
          f
        `);
        f.callSyncifying();
    }
    test4();
}
main();
