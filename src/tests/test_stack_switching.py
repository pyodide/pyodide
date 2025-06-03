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


@pytest.mark.xfail_browsers(node="Scopes don't work as needed")
def test_syncify_not_supported(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    selenium.run_js(
        """
        // Ensure that it's not supported by deleting WebAssembly.Suspender
        delete WebAssembly.Suspender;
        delete WebAssembly.Suspending;
        let pyodide = await loadPyodide({});
        await assertThrowsAsync(
          async () => await pyodide._api.pyodide_code.eval_code.callPromising("1+1"),
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
            with pytest.raises(RuntimeError, match="Cannot stack switch"):
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
@pytest.mark.xfail(reason="Requires wasm replacement for stub trampolines")
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
                const ptr = await Module.createPromising(catchlib.promising_catch_call_pyobj)(x);
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
        await Promise.all([f.callPromising("a", 15), f.callPromising("b", 25)])
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
            b.callPromising(300),
            b.callPromising(200),
            b.callPromising(250),
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
            return await g1.callPromising();
        }
        async function f2() {
            await sleep(30);
            return await g2.callPromising();
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
        p.push(g.callPromising().then((res) => l.append(res)));
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


@requires_jspi
def test_throw_from_switcher(selenium):
    """
    This used to fail because because a()'s error status got stolen by b(). This
    happens because the promising function is a separate task from the js code
    in callPyObjectSuspending, so the sequence of events goes:

    - enter main task,
        - enter callPyObjectSuspending(a)
            - enter promisingApply(a)
            - sets error flag and returns NULL
        - queue continue callPyObjectSuspending(a) in event loop
          now looks like [main task, continue callPyObjectSuspending(a)]

        - enter b()
            - enter Python
            - returns 7 with error state still set
        - rejects with "SystemError: <function b at 0x1140f20> returned a result with an exception set"
    - queue continue main() in event loop
    - continue callPyObjectSuspending(a)
        - pythonexc2js called attempting to read error flag set by promisingApply(a), fails with
          PythonError: TypeError: Pyodide internal error: no exception type or value

    The solution: at the end of `_pyproxy_apply_promising` we move the error
    flag into errStatus argument. In callPyObjectSuspending when we're ready we
    move the error back from the errorStatus variable into the error flag before
    calling `pythonexc2js()`
    """
    selenium.run_js(
        """
        pyodide.runPython(`
            def a():
                raise Exception("hi")
            def b():
                return 7;
        `);
        const a = pyodide.globals.get("a");
        const b = pyodide.globals.get("b");
        const p = a.callPromising();
        assert(() => b() === 7);
        await assertThrowsAsync(async () => await p, "PythonError", "Exception: hi");
        a.destroy();
        b.destroy();
        """
    )


@requires_jspi
def test_switch_from_except_block(selenium):
    """Test for issue #4566"""
    result = selenium.run_js(
        """
        const result = [];
        pyodide.globals.set("result", result);
        pyodide.runPython(`
            from pyodide.ffi import run_sync, to_js
            import sys
            from js import sleep

            def pe(s):
                result.push(to_js([s, repr(sys.exception())]))

            def g(n):
                pe(f"{n}0")
                try:
                    raise Exception(n)
                except:
                    pe(f"{n}1")
                    run_sync(sleep(10))
                    pe(f"{n}2")
                pe(f"{n}3")
        `);
        const pe = pyodide.globals.get("pe");
        const g = pyodide.globals.get("g");
        const g1 = g.callPromising("a");
        const g2 = g.callPromising("b");
        pe('tt')
        await g1;
        await g2;
        pyodide.globals.delete("result");
        pe.destroy();
        g.destroy();
        return result;
        """
    )
    assert result == [
        ["a0", "None"],
        ["a1", "Exception('a')"],
        ["b0", "None"],
        ["b1", "Exception('b')"],
        ["tt", "None"],
        ["a2", "Exception('a')"],
        ["a3", "None"],
        ["b2", "Exception('b')"],
        ["b3", "None"],
    ]


# Start with just a no-op script
LEAK_SCRIPT1 = """
def test(n):
    pass
"""

LEAK_SCRIPT2 = """
from pyodide.ffi import run_sync
from js import sleep

def test(n):
    run_sync(sleep(1))
"""

LEAK_SCRIPT3 = """
from pyodide.ffi import run_sync
from asyncio import sleep as py_sleep, ensure_future

async def sleep(x):
    await py_sleep(x/1000)

def test(n):
    run_sync(ensure_future(sleep(1)))
"""

LEAK_SCRIPT4 = """
from pyodide.ffi import run_sync
from asyncio import sleep as py_sleep

async def sleep(x):
    await py_sleep(x/1000)

def test(n):
    run_sync(sleep(1))
"""


@pytest.mark.xfail_browsers(
    firefox="requires jspi", safari="requires jspi", chrome="mysterious crash"
)
@pytest.mark.parametrize(
    "script", [LEAK_SCRIPT1, LEAK_SCRIPT2, LEAK_SCRIPT3, LEAK_SCRIPT4]
)
def test_memory_leak(selenium, script):
    length_change = selenium.run_js(
        f"""
        pyodide.runPython(`{script}`);
        """
        """
        const t = pyodide.globals.get("test");
        for (let i = 0; i < 1; i++) {
            let p = [];
            // warm up first to avoid edge problems
            for (let i = 0; i < 200; i++) {
                p.push(t.callPromising(1));
            }
            await Promise.all(p);
        }
        const startLength = pyodide._module.HEAP32.length;
        for (let i = 0; i < 10; i++) {
            p = [];
            for (let i = 0; i < 200; i++) {
                p.push(t.callPromising(1));
            }
            await Promise.all(p);
        }
        t.destroy();
        return pyodide._module.HEAP32.length - startLength;
        """
    )
    assert length_change == 0


@requires_jspi
@run_in_pyodide
def test_run_until_complete(selenium):
    from asyncio import create_task, gather, get_event_loop, sleep

    from js import sleep as js_sleep
    from pyodide.code import run_js

    loop = get_event_loop()

    async def test():
        await sleep(0.1)
        return 7

    assert loop.run_until_complete(test()) == 7
    assert loop.run_until_complete(create_task(test())) == 7
    loop.run_until_complete(sleep(0.1))
    loop.run_until_complete(js_sleep(100))
    res = loop.run_until_complete(
        gather(test(), sleep(0.1), js_sleep(100), js_sleep(100))
    )
    assert list(res) == [7, None, None, None]
    p = run_js("[sleep(100).then(() => 99)]")[0]
    assert loop.run_until_complete(p) == 99


@requires_jspi
def test_can_run_sync(selenium):
    results = selenium.run_js(
        """
        const results = [];
        pyodide.globals.set("results", results);
        pyodide.runPython(`
            from pyodide.ffi import can_run_sync, to_js
            from pyodide.code import run_js
            def expect(n, val):
                results.append(to_js([n, can_run_sync(), val]))
        `)


        pyodide.runPython(`expect(0, False)`);

        await pyodide.runPythonAsync(`expect(1, True)`);

        pyodide.runPython(`
            def fsync():
               expect(2, False)
        `);
        const fsync = pyodide.globals.get("fsync");
        fsync();
        fsync.destroy();

        pyodide.runPython(`
            def fsync():
                expect(3, True)

            async def fasync():
                fsync()
                expect(4, True)
        `);
        const fasync = pyodide.globals.get("fasync");
        await fasync();
        fasync.destroy();

        await pyodide.runPythonAsync(`
            def fsync():
                expect(5, False)

            run_js("(f) => f()")(fsync)
        `);

        await pyodide.runPythonAsync(`
            def fsync():
                expect(6, True)

            async def fasync():
                fsync()
                expect(7, True)

            await run_js("(f) => f()")(fasync)
        `);

        await pyodide.runPythonAsync(`
            run_js("(x) => Array.from(x)")([])
            expect(8, True)
        `);

        return results;
        """
    )
    assert len(results) == 9
    for idx, [i, res, expected] in enumerate(results):
        assert idx == i
        assert res == expected


@requires_jspi
def test_async_promising_sync_error(selenium):
    import pytest

    with pytest.raises(selenium.JavascriptException, match="division by zero"):
        selenium.run_js(
            """
            const test = pyodide.runPython(`
                def test():
                    1/0

                test
            `)

            try {
                await test.callPromising();
            } finally {
                test.destroy();
            }
            """
        )
    # In bad cases, the previous exception was a fatal error but we didn't
    # notice. Check that no fatal error occurred by running Python.
    selenium.run("")


@requires_jspi
def test_async_promising_async_error(selenium):
    import pytest

    with pytest.raises(selenium.JavascriptException, match="division by zero"):
        selenium.run_js(
            """
            const test = pyodide.runPython(`
                async def test():
                    1/0

                test
            `)

            try {
                await test.callPromising();
            } finally {
                test.destroy();
            }
            """
        )
    # In bad cases, the previous exception was a fatal error but we didn't
    # notice. Check that no fatal error occurred by running Python.
    selenium.run("")
