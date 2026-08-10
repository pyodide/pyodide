import pytest
from pytest_pyodide import run_in_pyodide

from conftest import requires_jspi

STACK_CHECK_JS = """
return pyodide._module.stackSave();
"""

STACK_CHECK_AFTER_JS = """
let lastStack = Infinity;
let curStack = pyodide._module.stackSave();
pyodide.runPython("def nothing(): pass");
// Reset stack address
await pyodide.globals.nothing.callPromising();
return pyodide._module.stackSave();
"""


@pytest.fixture(autouse=True)
def assert_no_stack_leak(request):
    selenium = (
        request.getfixturevalue("selenium")
        if "selenium" in request.fixturenames
        else None
    )
    if selenium is None:
        yield
        return
    if selenium.browser in ("firefox", "safari"):
        yield
        return
    before = selenium.run_js(STACK_CHECK_JS)
    yield
    after = selenium.run_js(STACK_CHECK_AFTER_JS)
    assert before == after, (
        f"stack pointer leak: before={before} after={after} diff={before - after} bytes"
    )


@requires_jspi
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
@run_in_pyodide
def test_syncify_null(selenium):
    from pyodide.code import run_js
    from pyodide.ffi import jsnull, run_sync

    asyncNull = run_js(
        """
        (async function asyncThrow(){
            await sleep(50);
            return null;
        })
        """
    )
    assert run_sync(asyncNull()) is jsnull


@requires_jspi
@pytest.mark.requires_dynamic_linking
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
@run_in_pyodide(packages=["test-fpcast"])
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

            await pyodide.loadPackage("test-cpp-exceptions")
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
@pytest.mark.requires_dynamic_linking
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
        await Promise.all([f.callPromising("a", 15), f.callPromising("b", 21)])
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
        ["b", 1],
        ["a", 2],
        ["a", 3],
        ["b", 2],
        ["a", 4],
        ["b", 3],
        ["b", 4],
    ]


@requires_jspi
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
        await pe.callPromising('tt');
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


@pytest.mark.xfail_browsers(firefox="requires jspi", safari="requires jspi")
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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
@pytest.mark.requires_dynamic_linking
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


@pytest.mark.skip_refcount_check
@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_return_promising_no_crash(selenium):
    """This used to fatally fail.

    The fix was to incref ptrobj before await Module.promisingApply(...), so
    presumably the crash involved the pointer to g getting freed out from
    underneath? I'm honestly not sure how it worked.
    """
    selenium.run_js(
        """
        globalThis.f = function f() {
            return task.callPromising();
        };
        pyodide.runPython(`
            from asyncio import sleep
            from pyodide.ffi import run_sync

            def task():
                run_sync(sleep(1))

            def g():
                from js import f
                return f()
        `);
        const task = pyodide.globals.get("task");
        const g = pyodide.globals.get("g");
        await Promise.all([g(), g()]);
        g.destroy();
        task.destroy();
        """
    )


# The following tests cover the thread state ownership model described at the
# top of src/core/stack_switching/pystate.c. A promising task owns a thread
# state of its own for its whole lifetime.

SUSPEND_ON_PROMISE_SETUP = """
    pyodide.runPython(`
        from pyodide.ffi import run_sync

        def suspend_on(p, before=None, after=None):
            if before is not None:
                before()
            run_sync(p)
            if after is not None:
                return after()
    `);
    // Start a promising call that suspends until we resolve the returned
    // trigger. Waits until the task has really suspended before returning.
    const suspend_on = pyodide.globals.get("suspend_on");
    async function startSuspendedTask(before, after) {
        let resolve;
        const p = new Promise((res) => { resolve = res; });
        const done = suspend_on.callPromising(p, before, after);
        // callPromising yields to the event loop before it even enters Python, so
        // we have to wait for the task to actually reach run_sync().
        await new Promise((res) => setTimeout(res, 50));
        return { resolve, done };
    }
"""


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_contextvars_ambient_context_survives_switch(selenium):
    """The context of the event loop turn must not be carried off by a task.

    Previously the suspending task took the caller's thread state with it and
    handed the caller a brand new one, so top level code lost its contextvars for
    the duration of the switch.
    """
    result = selenium.run_js(
        """
        pyodide.runPython(`
            import contextvars
            cvar = contextvars.ContextVar("cvar", default="<lost>")
            cvar.set("TOP-LEVEL")
            observe = lambda: cvar.get()
            copied = lambda: contextvars.copy_context().get(cvar, "<absent>")
        `);
        """
        + SUSPEND_ON_PROMISE_SETUP
        + """
        const observe = pyodide.globals.get("observe");
        const copied = pyodide.globals.get("copied");
        const out = { before: observe() };
        const task = await startSuspendedTask();
        out.during = observe();
        out.duringCopyContext = copied();
        task.resolve();
        await task.done;
        out.after = observe();
        suspend_on.destroy();
        observe.destroy();
        copied.destroy();
        return out;
        """
    )
    assert result == {
        "before": "TOP-LEVEL",
        "during": "TOP-LEVEL",
        "duringCopyContext": "TOP-LEVEL",
        "after": "TOP-LEVEL",
    }


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_contextvars_survive_interleaved_switches(selenium):
    """Stack switches are not properly nested.

    Resume A, finish A, then resume B. Previously each resume destroyed whichever
    thread state happened to be current, so the event loop's thread state ended up
    recycled and top level contextvars and threading.local() state were lost.
    """
    result = selenium.run_js(
        """
        pyodide.runPython(`
            import contextvars, threading
            cvar = contextvars.ContextVar("cvar", default="<lost>")
            cvar.set("TOP-LEVEL")
            tls = threading.local()
            tls.value = "TOP-LEVEL-TLS"
            def observe():
                return [cvar.get(), getattr(tls, "value", "<lost>")]
        `);
        """
        + SUSPEND_ON_PROMISE_SETUP
        + """
        const observe = pyodide.globals.get("observe");
        const a = await startSuspendedTask();
        const b = await startSuspendedTask();
        // Deliberately not LIFO.
        a.resolve();
        await a.done;
        b.resolve();
        await b.done;
        const observed = observe();
        const out = observed.toJs();
        observed.destroy();
        suspend_on.destroy();
        observe.destroy();
        return out;
        """
    )
    assert result == ["TOP-LEVEL", "TOP-LEVEL-TLS"]


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_contextvars_task_writes_are_isolated(selenium):
    """A task inherits a *copy* of its caller's context, like asyncio.Task does.

    So it can read what the caller set, but its own writes don't leak back out to
    the caller or into any later task. Previously a task's writes leaked out
    through the recycled thread state and showed up in a completely unrelated
    stack switch.
    """
    result = selenium.run_js(
        """
        pyodide.runPython(`
            import contextvars
            cvar = contextvars.ContextVar("cvar", default="<default>")
            cvar.set("CALLER")
            observe = lambda: cvar.get()
            def poison():
                cvar.set("TASK-ONLY")
        `);
        """
        + SUSPEND_ON_PROMISE_SETUP
        + """
        const observe = pyodide.globals.get("observe");
        const poison = pyodide.globals.get("poison");
        const out = {};
        // A task that reads the caller's context, then overwrites it and keeps the
        // value set across a suspension.
        let task = await startSuspendedTask(poison, observe);
        task.resolve();
        out.insideTask = await task.done;
        out.callerAfterTask = observe();
        // A second, unrelated task must not see the first task's write. It reuses
        // the first task's thread state via the freelist.
        task = await startSuspendedTask(undefined, observe);
        task.resolve();
        out.insideLaterTask = await task.done;
        suspend_on.destroy();
        observe.destroy();
        poison.destroy();
        return out;
        """
    )
    assert result == {
        "insideTask": "TASK-ONLY",
        "callerAfterTask": "CALLER",
        "insideLaterTask": "CALLER",
    }


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_contextvars_released_after_task(selenium):
    """A recycled thread state must not pin the context it used to hold."""
    alive = selenium.run_js(
        """
        pyodide.runPython(`
            import contextvars, gc, weakref
            cvar = contextvars.ContextVar("cvar", default=None)
            ref = None
            class Big:
                pass
            def poison():
                global ref
                o = Big()
                ref = weakref.ref(o)
                cvar.set(o)
            def still_alive():
                gc.collect()
                return ref() is not None
        `);
        """
        + SUSPEND_ON_PROMISE_SETUP
        + """
        const poison = pyodide.globals.get("poison");
        const still_alive = pyodide.globals.get("still_alive");
        let task = await startSuspendedTask(poison);
        task.resolve();
        await task.done;
        // Churn enough tasks to push the thread state out of the freelist too.
        for (let i = 0; i < 15; i++) {
            task = await startSuspendedTask();
            task.resolve();
            await task.done;
        }
        const out = still_alive();
        suspend_on.destroy();
        poison.destroy();
        still_alive.destroy();
        return out;
        """
    )
    assert alive is False


@requires_jspi
@pytest.mark.requires_dynamic_linking
@run_in_pyodide
async def test_contextvars_concurrent_tasks(selenium):
    """Concurrent coroutines that syncify in the middle must not see each other's
    contextvars, and tasks they spawn must inherit the right context."""
    import asyncio
    import contextvars

    from js import sleep as js_sleep
    from pyodide.ffi import run_sync

    request_id = contextvars.ContextVar("request_id", default="<none>")

    async def handle(rid, delay):
        request_id.set(rid)
        run_sync(js_sleep(delay))
        assert request_id.get() == rid, f"after run_sync: {request_id.get()}"

        async def child():
            return request_id.get()

        assert await asyncio.ensure_future(child()) == rid
        return request_id.get()

    # B finishes its switch before A does, so the two switches interleave.
    assert list(await asyncio.gather(handle("REQ-A", 60), handle("REQ-B", 20))) == [
        "REQ-A",
        "REQ-B",
    ]
    assert request_id.get() == "<none>"


@requires_jspi
@pytest.mark.requires_dynamic_linking
@run_in_pyodide
def test_asyncio_running_loop_in_task(selenium):
    """The running event loop lives on the thread state, so a task with a thread
    state of its own has to inherit it from its caller."""
    import asyncio

    from pyodide.code import run_js

    loop = asyncio.get_event_loop()

    async def test():
        assert asyncio.get_running_loop() is loop
        p = run_js("[sleep(50).then(() => 11)]")[0]
        from pyodide.ffi import run_sync

        assert run_sync(p) == 11
        assert asyncio.get_running_loop() is loop
        return 5

    assert loop.run_until_complete(test()) == 5


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_contextvars_three_interleaved_tasks(selenium):
    """Three tasks, each suspending twice, resumed in an order unrelated to the
    order they suspended in.

    Each task must keep seeing its own contextvar value across both of its
    suspensions, must have inherited the caller's value on entry, and must not
    disturb the caller's value or each other's.
    """
    result = selenium.run_js(
        """
        pyodide.runPython(`
            import contextvars
            from pyodide.ffi import run_sync
            cvar = contextvars.ContextVar("cvar", default="<unset>")
            cvar.set("ROOT")

            def task(name, first, second):
                inherited = cvar.get()
                cvar.set(name)
                run_sync(first)
                after_first = cvar.get()
                run_sync(second)
                return [inherited, after_first, cvar.get()]

            observe = lambda: cvar.get()
        `);
        const task = pyodide.globals.get("task");
        const observe = pyodide.globals.get("observe");
        const tick = () => new Promise((res) => setTimeout(res, 50));

        // Start a task and wait for it to reach its first run_sync().
        const started = {};
        function start(name) {
            let first, second;
            const p1 = new Promise((res) => { first = res; });
            const p2 = new Promise((res) => { second = res; });
            const done = task.callPromising(name, p1, p2);
            started[name] = { first, second, done };
        }
        start("A");
        start("B");
        start("C");
        await tick();
        const duringAll = observe();

        // Release the first suspension in a different order than they started.
        started.C.first();
        await tick();
        started.A.first();
        await tick();
        started.B.first();
        await tick();
        const duringSecond = observe();

        // And the second suspension in yet another order.
        started.B.second();
        started.C.second();
        started.A.second();
        const out = {};
        for (const name of ["A", "B", "C"]) {
            const res = await started[name].done;
            out[name] = res.toJs();
            res.destroy();
        }
        out.duringAll = duringAll;
        out.duringSecond = duringSecond;
        out.atEnd = observe();
        task.destroy();
        observe.destroy();
        return out;
        """
    )
    assert result == {
        # Each task inherits ROOT, then only ever sees its own value.
        "A": ["ROOT", "A", "A"],
        "B": ["ROOT", "B", "B"],
        "C": ["ROOT", "C", "C"],
        # The event loop turn keeps its own context the whole way through.
        "duringAll": "ROOT",
        "duringSecond": "ROOT",
        "atEnd": "ROOT",
    }


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_contextvars_task_spawned_from_running_task(selenium):
    """Two parent tasks that each re-enter Python from JS while running.

    A1 suspends, B1 suspends, A1 resumes and calls out to JS which uses
    callPromising() to call back into Python and start A2 (without awaiting it),
    A1 suspends again, A2 starts and suspends. Same for B1/B2. Then they exit in
    the order A1, B1, A2, B2, i.e. the parents finish before their children and
    nothing unwinds in the order it was created.

    Note that A2 inherits the event loop turn's context, not A1's, even though
    A1 is what triggered it. It means callPromising() behaves like "spawn on the
    event loop" rather than like loop.call_soon(), which captures the caller's
    context.
    """
    order, results, observations = selenium.run_js(
        """
        const results = [];
        const observations = {};
        pyodide.globals.set("results", results);
        pyodide.runPython(`
            import contextvars
            from pyodide.ffi import run_sync, to_js
            cvar = contextvars.ContextVar("cvar", default="<unset>")
            cvar.set("ROOT")

            def parent(name, first, second, spawn):
                inherited = cvar.get()
                cvar.set(name)
                run_sync(first)
                # Re-enter Python from JS while we are running. This returns a
                # pending promise; we deliberately don't wait for the child.
                spawn()
                mid = cvar.get()
                run_sync(second)
                results.append(to_js([name, inherited, mid, cvar.get()]))
                return name

            def child(name, only):
                inherited = cvar.get()
                cvar.set(name)
                run_sync(only)
                results.append(to_js([name, inherited, cvar.get()]))
                return name

            observe = lambda: cvar.get()
        `);
        const parent = pyodide.globals.get("parent");
        const child = pyodide.globals.get("child");
        const observe = pyodide.globals.get("observe");
        const tick = () => new Promise((res) => setTimeout(res, 50));

        function trigger() {
            let release;
            const promise = new Promise((res) => { release = res; });
            return { promise, release };
        }
        const a1 = { first: trigger(), second: trigger() };
        const b1 = { first: trigger(), second: trigger() };
        const a2 = trigger();
        const b2 = trigger();

        const order = [];
        const children = {};
        // Handed to Python and called from inside the running parent.
        function spawn(name, t) {
            return () => {
                children[name] = child.callPromising(name, t.promise);
            };
        }

        const a1done = parent.callPromising(
            "A1", a1.first.promise, a1.second.promise, spawn("A2", a2));
        await tick();
        const b1done = parent.callPromising(
            "B1", b1.first.promise, b1.second.promise, spawn("B2", b2));
        await tick();
        observations.a1AndB1Suspended = observe();

        // A1 resumes, spawns A2, suspends again; then A2 starts and suspends.
        a1.first.release();
        await tick();
        // Same for B1/B2.
        b1.first.release();
        await tick();
        observations.allFourSuspended = observe();

        // Exit A1, B1, A2, B2 -- parents before children.
        a1.second.release();
        order.push(await a1done);
        await tick();
        observations.afterA1AndNothingElse = observe();

        b1.second.release();
        order.push(await b1done);
        await tick();
        observations.afterBothParents = observe();

        a2.release();
        order.push(await children.A2);
        await tick();
        observations.afterA2 = observe();

        b2.release();
        order.push(await children.B2);
        await tick();
        observations.atEnd = observe();

        parent.destroy();
        child.destroy();
        observe.destroy();
        return [order, results, observations];
        """
    )
    assert order == ["A1", "B1", "A2", "B2"]
    # [name, context inherited on entry, ...context seen after each suspension]
    assert sorted(results) == [
        ["A1", "ROOT", "A1", "A1"],
        ["A2", "ROOT", "A2"],
        ["B1", "ROOT", "B1", "B1"],
        ["B2", "ROOT", "B2"],
    ]
    # The event loop turn keeps its own context no matter how the four tasks
    # interleave, including after some of them have exited.
    assert observations == {
        "a1AndB1Suspended": "ROOT",
        "allFourSuspended": "ROOT",
        "afterA1AndNothingElse": "ROOT",
        "afterBothParents": "ROOT",
        "afterA2": "ROOT",
        "atEnd": "ROOT",
    }


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_thread_state_not_reused_between_tasks(selenium):
    """A task must not inherit anything from an unrelated task that ran before.

    threading.local() storage hangs off tstate->threading_local_key rather than
    off the thread dict, so it follows thread state identity.
    """
    seen, top_level = selenium.run_js(
        """
        pyodide.runPython(`
            import threading
            from pyodide.ffi import run_sync
            loc = threading.local()

            def task(name, p):
                before = getattr(loc, "v", "<unset>")
                loc.v = name
                run_sync(p)
                return before
        `);
        const task = pyodide.globals.get("task");
        const seen = [];
        // Run the tasks one after another so each one is free to pick up the
        // thread state the previous one finished with.
        for (const name of ["A", "B", "C"]) {
            let release;
            const promise = new Promise((res) => { release = res; });
            const done = task.callPromising(name, promise);
            await new Promise((res) => setTimeout(res, 20));
            release();
            seen.push(await done);
        }
        task.destroy();
        return [seen, pyodide.runPython(`getattr(loc, "v", "<unset>")`)];
        """
    )
    # Every task starts with an empty threading.local(), including after two
    # other tasks have set a value and exited.
    assert seen == ["<unset>", "<unset>", "<unset>"]
    # ...and top level never sees the tasks' values either.
    assert top_level == "<unset>"


@requires_jspi
@pytest.mark.requires_dynamic_linking
def test_task_inherits_asyncgen_hooks(selenium):
    """sys.set_asyncgen_hooks() applies inside promising tasks.

    The hooks are recorded on the thread state, and a task runs on a thread
    state of its own, so it has to inherit them from its caller. Otherwise an
    async generator created inside a task is never handed to the hook that is
    supposed to arrange for it to be closed.
    """
    seen = selenium.run_js(
        """
        pyodide.runPython(`
            import sys
            from pyodide.ffi import run_sync

            seen = []

            async def agen():
                yield 1

            def drive():
                # Start the async generator on this thread state. The firstiter
                # hook fires on the first __anext__().
                g = agen()
                try:
                    g.__anext__().send(None)
                except StopIteration:
                    pass

            def task(p):
                # Suspend and resume first, so we also cover the hooks
                # surviving a round trip through the event loop.
                run_sync(p)
                drive()
                return seen

            sys.set_asyncgen_hooks(
                firstiter=lambda ag: seen.append(ag.__name__),
                finalizer=lambda ag: None,
            )
        `);
        const task = pyodide.globals.get("task");
        let release;
        const promise = new Promise((res) => { release = res; });
        const done = task.callPromising(promise);
        await new Promise((res) => setTimeout(res, 20));
        release();
        const res = await done;
        const out = res.toJs();
        res.destroy();
        task.destroy();
        return out;
        """
    )
    assert seen == ["agen"]
