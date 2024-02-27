import pytest
from pytest_pyodide import run_in_pyodide

from conftest import requires_jspi


@requires_jspi
@run_in_pyodide
def test_syncify_awaitable_types_accept(selenium):
    from asyncio import create_task, gather, sleep

    from js import sleep as js_sleep
    from pyodide.code import run_js
    from pyodide.ffi import run_sync

    async def test():
        await sleep(0.1)
        return 7

    assert run_sync(test()) == 7
    assert run_sync(create_task(test())) == 7
    run_sync(sleep(0.1))
    run_sync(js_sleep(100))
    res = run_sync(gather(test(), sleep(0.1), js_sleep(100), js_sleep(100)))
    assert list(res) == [7, None, None, None]
    p = run_js("[sleep(100)]")[0]
    run_sync(p)


@requires_jspi
@run_in_pyodide
def test_syncify_awaitable_type_errors(selenium):
    import pytest

    from pyodide.ffi import run_sync

    with pytest.raises(TypeError):
        run_sync(1)  # type:ignore[arg-type]
    with pytest.raises(TypeError):
        run_sync(None)  # type:ignore[arg-type]
    with pytest.raises(TypeError):
        run_sync([1, 2, 3])  # type:ignore[arg-type]
    with pytest.raises(TypeError):
        run_sync(iter([1, 2, 3]))  # type:ignore[arg-type]

    def f():
        yield 1
        yield 2
        yield 3

    with pytest.raises(TypeError):
        run_sync(f())


@pytest.mark.skip(reason="FIXME!")
def test_throw_from_switcher(selenium):
    """
    Currently failing:

    Uncaught PythonError: Traceback (most recent call last):
      File "<exec>", line 9, in b
    Exception: hi

    The above exception was the direct cause of the following exception:

    SystemError: <function a at 0x9aaea0> returned a result with an exception set
    """
    selenium.run_js(
        """
        pyodide.runPython(`
            async def a():
                pass

            def b():
                raise Exception("hi")
        `);

        const a = pyodide.globals.get("a");
        const b = pyodide.globals.get("b");

        await Promise.all([
            b.callSyncifying(),
            a(),
        ]);
        """
    )


@pytest.mark.xfail_browsers(node="Scopes don't work as needed")
def test_syncify_not_supported1(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        // Ensure that it's not supported by deleting WebAssembly.Suspender
        delete WebAssembly.Suspender;
        let pyodide = await loadPyodide({});
        await assertThrowsAsync(
          async () => await pyodide._api.pyodide_code.eval_code.callSyncifying("1+1"),
          "Error",
          "WebAssembly stack switching not supported in this JavaScript runtime"
        );
        await assertThrows(
          () => pyodide.runPython(`
            from pyodide.ffi import run_sync
            run_sync(1)
          `),
          "PythonError",
          "RuntimeError: WebAssembly stack switching not supported in this JavaScript runtime"
        );
        """
    )


@pytest.mark.xfail_browsers(
    node="Scopes don't work as needed", safari="Doesn't have WebAssembly.Function?"
)
def test_syncify_not_supported2(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        // Disable direct instantiation of WebAssembly.Modules
        // Note: only will work with newer runtimes that have WebAssembly.Function
        WebAssembly.Module = new Proxy(WebAssembly.Module, {construct(){throw new Error("NOPE!");}});
        let pyodide = await loadPyodide({});
        await assertThrowsAsync(
          async () => await pyodide._api.pyodide_code.eval_code.callSyncifying("1+1"),
          "Error",
          "WebAssembly stack switching not supported in this JavaScript runtime"
        );
        await assertThrows(
          () => pyodide.runPython(`
            from pyodide.ffi import run_sync
            run_sync(1)
          `),
          "PythonError",
          "RuntimeError: WebAssembly stack switching not supported in this JavaScript runtime"
        );
        """
    )


@requires_jspi
@run_in_pyodide
def test_syncify1(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import run_sync

    test = run_js(
        """
        (async function test() {
            await sleep(1000);
            return 7;
        })
        """
    )
    assert run_sync(test()) == 7


@requires_jspi
@run_in_pyodide(packages=["pytest"])
def test_syncify2(selenium):
    import importlib.metadata

    import pytest

    from pyodide.ffi import run_sync
    from pyodide_js import loadPackage

    with pytest.raises(ModuleNotFoundError):
        importlib.metadata.version("micropip")

    run_sync(loadPackage("micropip"))

    assert importlib.metadata.version("micropip")


@requires_jspi
@run_in_pyodide(packages=["pytest"])
def test_syncify_error(selenium):
    import pytest

    from pyodide.code import run_js
    from pyodide.ffi import JsException, run_sync

    asyncThrow = run_js(
        """
        (async function asyncThrow(){
            throw new Error("hi");
        })
        """
    )

    with pytest.raises(JsException, match="hi"):
        run_sync(asyncThrow())


@requires_jspi
@run_in_pyodide
def test_syncify_null(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import run_sync

    asyncNull = run_js(
        """
        (async function asyncThrow(){
            await sleep(50);
            return null;
        })
        """
    )
    assert run_sync(asyncNull()) is None


@requires_jspi
def test_syncify_no_suspender(selenium):
    selenium.run_js(
        """
        await pyodide.loadPackage("pytest");
        pyodide.runPython(`
            from pyodide.code import run_js
            from pyodide.ffi import run_sync
            import pytest

            test = run_js(
                '''
                (async function test() {
                    await sleep(1000);
                    return 7;
                })
                '''
            )
            with pytest.raises(RuntimeError, match="No suspender"):
                run_sync(test())
            del test
        `);
        """
    )


@pytest.mark.requires_dynamic_linking
@requires_jspi
@run_in_pyodide(packages=["fpcast-test"])
def test_syncify_getset(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import run_sync

    test = run_js(
        """
        (async function test() {
            await sleep(1000);
            return 7;
        })
        """
    )
    x = []

    def wrapper():
        x.append(run_sync(test()))

    import fpcast_test

    t = fpcast_test.TestType()
    t.getset_jspi_test = wrapper
    t.getset_jspi_test  # noqa: B018
    t.getset_jspi_test = None
    assert x == [7, 7]


@requires_jspi
@pytest.mark.requires_dynamic_linking
@pytest.mark.skip(reason="Will fix in a followup")
@run_in_pyodide
def test_syncify_ctypes(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import run_sync

    test = run_js(
        """
        (async function test() {
            await sleep(1000);
            return 7;
        })
        """
    )

    def wrapper():
        return run_sync(test())

    from ctypes import py_object, pythonapi

    pythonapi.PyObject_CallNoArgs.argtypes = [py_object]
    pythonapi.PyObject_CallNoArgs.restype = py_object
    assert pythonapi.PyObject_CallNoArgs(wrapper) == 7


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_cpp_exceptions_and_syncify(selenium):
    assert (
        selenium.run_js(
            """
            ptr = pyodide.runPython(`
                from pyodide.ffi import run_sync
                from pyodide.code import run_js
                temp = run_js(
                    '''
                    (async function temp() {
                        await sleep(100);
                        return 9;
                    })
                    '''
                )

                def f():
                    try:
                        return run_sync(temp())
                    except Exception as e:
                        print(e)
                        return -1
                id(f)
            `);

            await pyodide.loadPackage("cpp-exceptions-test")
            const Module = pyodide._module;
            const catchlib = pyodide._module.LDSO.loadedLibsByName["/usr/lib/cpp-exceptions-test-catch.so"].exports;
            async function t(x){
                Module.validSuspender.value = true;
                const ptr = await Module.createPromising(catchlib.catch_call_pyobj)(x);
                Module.validSuspender.value = false;
                const res = Module.UTF8ToString(ptr);
                Module._free(ptr);
                return res;
            }
            return await t(ptr)
            """
        )
        == "result was: 9"
    )


@requires_jspi
def test_two_way_transfer(selenium):
    res = selenium.run_js(
        """
        pyodide.runPython(`
            from pyodide.ffi import run_sync
            l = []
            def f(n, t):
                from js import sleep
                for i in range(5):
                    run_sync(sleep(t))
                    l.append([n, i])
        `);
        f = pyodide.globals.get("f");
        await Promise.all([f.callSyncifying("a", 15), f.callSyncifying("b", 25)])
        f.destroy();
        const l = pyodide.globals.get("l");
        const res = l.toJs();
        l.destroy();
        return res;
        """
    )
    assert res == [
        ["a", 0],
        ["b", 0],
        ["a", 1],
        ["a", 2],
        ["b", 1],
        ["a", 3],
        ["b", 2],
        ["a", 4],
        ["b", 3],
        ["b", 4],
    ]


@requires_jspi
def test_sync_async_mix(selenium):
    res = selenium.run_js(
        """
        pyodide.runPython(`
            from pyodide.ffi import run_sync
            from js import sleep

            l = [];
            async def a(t):
                await sleep(t)
                l.append(["a", t])

            def b(t):
                run_sync(sleep(t))
                l.append(["b", t])
        `);
        const a = pyodide.globals.get("a");
        const b = pyodide.globals.get("b");
        const l = pyodide.globals.get("l");

        await Promise.all([
            b.callSyncifying(300),
            b.callSyncifying(200),
            b.callSyncifying(250),
            a(220),
            a(150),
            a(270)
        ]);
        const res = l.toJs();
        for(let p of [a, b, l]) {
            p.destroy();
        }
        return res;
        """
    )
    assert res == [
        ["a", 150],
        ["b", 200],
        ["a", 220],
        ["b", 250],
        ["a", 270],
        ["b", 300],
    ]


@requires_jspi
def test_nested_syncify(selenium):
    res = selenium.run_js(
        """
        async function f1() {
            await sleep(30);
            return await g1.callSyncifying();
        }
        async function f2() {
            await sleep(30);
            return await g2.callSyncifying();
        }
        async function getStuff() {
            await sleep(30);
            return "gotStuff";
        }
        pyodide.globals.set("f1", f1);
        pyodide.globals.set("f2", f2);
        pyodide.globals.set("getStuff", getStuff);

        pyodide.runPython(`
            from pyodide.ffi import run_sync
            from js import sleep
            def g():
                run_sync(sleep(25))
                return run_sync(f1())

            def g1():
                run_sync(sleep(25))
                return run_sync(f2())

            def g2():
                run_sync(sleep(25))
                return run_sync(getStuff())
        `);
        const l = pyodide.runPython("l = []; l")
        const g = pyodide.globals.get("g");
        const g1 = pyodide.globals.get("g1");
        const g2 = pyodide.globals.get("g2");
        const p = [];
        p.push(g.callSyncifying().then((res) => l.append(res)));
        p.push(pyodide.runPythonAsync(`
            from js import sleep
            for i in range(20):
                run_sync(sleep(9))
                l.append(i)
        `));
        await Promise.all(p);
        const res = l.toJs();
        for(let p of [l, g, g1, g2]) {
            p.destroy()
        }
        return res;
        """
    )
    assert "gotStuff" in res
    del res[res.index("gotStuff")]
    assert res == list(range(20))


@requires_jspi
@run_in_pyodide
async def test_promise_methods(selenium):
    from asyncio import sleep

    from pyodide.code import run_js
    from pyodide.ffi import run_sync

    async_pass = run_js(
        """
        (async function() {
            return 7;
        })
        """
    )

    async_raise = run_js(
        """
        (async function() {
            throw new Error("oops!");
        })
        """
    )

    def f(*args):
        print("will sleep")
        run_sync(sleep(0.1))
        print("have slept")

    await async_pass().then(f, f)
    await async_raise().then(f, f)
    await async_pass().finally_(f)
