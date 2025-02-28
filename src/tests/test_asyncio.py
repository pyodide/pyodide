import asyncio
import re
import time
from textwrap import dedent

import pytest
from pytest_pyodide import run_in_pyodide

from pyodide.code import eval_code_async
from conftest import PYODIDE_ROOT


def test_await_jsproxy(selenium):
    selenium.run(
        """
        def prom(res,rej):
            global resolve
            resolve = res
        from js import Promise
        from pyodide.ffi import create_once_callable
        p = Promise.new(create_once_callable(prom))
        async def temp():
            x = await p
            return x + 7
        resolve(10)
        c = temp()
        r = c.send(None)
        """
    )
    time.sleep(0.01)
    msg = "StopIteration: 17"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            c.send(r.result())
            """
        )


def test_then_jsproxy(selenium):
    selenium.run(
        """
        def prom(res, rej):
            global resolve
            global reject
            resolve = res
            reject = rej

        from js import Promise
        from pyodide.ffi import create_once_callable
        result = None
        err = None
        finally_occurred = False

        def onfulfilled(value):
            global result
            result = value

        def onrejected(value):
            global err
            err = value

        def onfinally():
            global finally_occurred
            finally_occurred = True
        """
    )

    selenium.run(
        """
        p = Promise.new(create_once_callable(prom))
        p.then(onfulfilled, onrejected)
        resolve(10)
        """
    )
    time.sleep(0.01)
    selenium.run(
        """
        assert result == 10
        assert err is None
        result = None
        """
    )

    selenium.run(
        """
        p = Promise.new(create_once_callable(prom))
        p.then(onfulfilled, onrejected)
        reject(10)
        """
    )
    time.sleep(0.01)
    selenium.run(
        """
        assert result is None
        assert err == 10
        err = None
        """
    )

    selenium.run(
        """
        p = Promise.new(create_once_callable(prom))
        p.catch(onrejected)
        resolve(10)
        """
    )
    time.sleep(0.01)
    selenium.run("assert err is None")

    selenium.run(
        """
        p = Promise.new(create_once_callable(prom))
        p.catch(onrejected)
        reject(10)
        """
    )
    time.sleep(0.01)
    selenium.run(
        """
        assert err == 10
        err = None
        """
    )

    selenium.run(
        """
        p = Promise.new(create_once_callable(prom))
        p.finally_(onfinally)
        resolve(10)
        """
    )
    time.sleep(0.01)
    selenium.run(
        """
        assert finally_occurred
        finally_occurred = False
        """
    )

    selenium.run(
        """
        p = Promise.new(create_once_callable(prom))
        p.finally_(onfinally).catch(onrejected) # node gets angry if we don't catch it!
        reject(10)
        """
    )
    time.sleep(0.01)
    selenium.run(
        """
        assert finally_occurred
        finally_occurred = False
        assert err == 10
        err = None
        """
    )


def test_await_fetch(selenium):
    selenium.run(
        """
        from js import fetch
        async def test():
            response = await fetch("console.html")
            result = await response.text()
            print(result)
            return result

        c = test()
        r1 = c.send(None)
        """
    )
    time.sleep(0.1)
    selenium.run(
        """
        r2 = c.send(r1.result())
        """
    )
    time.sleep(0.1)
    msg = "StopIteration: <!doctype html>"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            c.send(r2.result())
            """
        )


def test_await_error(selenium):
    selenium.run_js(
        """
        async function async_js_raises(){
            throw new Error("This is an error message!");
        }
        self.async_js_raises = async_js_raises;
        pyodide.runPython(`
            from js import async_js_raises
            async def test():
                c = await async_js_raises()
                return c
            c = test()
            r1 = c.send(None)
        `);
        """
    )
    msg = "This is an error message!"
    with pytest.raises(selenium.JavascriptException, match=msg):
        # Wait for event loop to go around for chome
        selenium.run(
            """
            try:
                r2 = c.send(r1.result())
            finally:
                del async_js_raises
            """
        )


def test_eval_code_async_simple():
    c = eval_code_async("1+92")
    with pytest.raises(StopIteration, match="93"):
        c.send(None)


def test_eval_code_async_loop():
    async def slow_identity(i):
        await asyncio.sleep(0.1)
        return i

    c = eval_code_async(
        """
        tot = 0
        for i in range(10):
            tot += await slow_identity(i)
        tot
        """,
        globals=globals(),
        locals=locals(),
    )
    fut = asyncio.ensure_future(c)
    asyncio.get_event_loop().run_until_complete(fut)
    assert fut.result() == 45


def test_eval_code_await_jsproxy(selenium):
    selenium.run(
        """
        def prom(res,rej):
            global resolve
            resolve = res
        from js import Promise
        from pyodide.ffi import create_once_callable
        p = Promise.new(create_once_callable(prom))
        from pyodide.code import eval_code_async
        c = eval_code_async(
            '''
            x = await p
            x + 7
            ''',
            globals=globals()
        )
        resolve(10)
        r = c.send(None)
        """
    )
    time.sleep(0.01)
    msg = "StopIteration: 17"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            c.send(r.result())
            """
        )


def test_eval_code_await_fetch(selenium):
    selenium.run(
        """
        from js import fetch
        from pyodide.code import eval_code_async
        c = eval_code_async(
            '''
            response = await fetch("console.html")
            await response.text()
            ''',
            globals=globals()
        )
        r1 = c.send(None)
        """
    )
    time.sleep(0.1)
    selenium.run(
        """
        r2 = c.send(r1.result())
        """
    )
    time.sleep(0.1)
    msg = "StopIteration: <!doctype html>"
    with pytest.raises(selenium.JavascriptException, match=msg):
        selenium.run(
            """
            c.send(r2.result())
            """
        )


def test_eval_code_await_error(selenium):
    selenium.run_js(
        """
        async function async_js_raises(){
            console.log("Hello there???");
            throw new Error("This is an error message!");
        }
        self.async_js_raises = async_js_raises;
        pyodide.runPython(`
            from js import async_js_raises
            from pyodide.code import eval_code_async
            c = eval_code_async(
                '''
                await async_js_raises()
                ''',
                globals=globals()
            )
            r1 = c.send(None)
        `)
        """
    )
    msg = "This is an error message!"
    with pytest.raises(selenium.JavascriptException, match=msg):
        # Wait for event loop to go around for chome
        selenium.run(
            """
            r2 = c.send(r1.result())
            """
        )


def test_ensure_future_memleak(selenium):
    selenium.run_js(
        """
        self.o = { "xxx" : 777 };
        pyodide.runPython(`
            import asyncio
            from js import o
            async def test():
                return o
            asyncio.ensure_future(test())
            None
        `);
        """
    )


def test_await_pyproxy_eval_async(selenium):
    assert (
        selenium.run_js(
            """
            let c = pyodide._api.pyodide_code.eval_code_async("1+1");
            let result = await c;
            c.destroy();
            return result;
            """
        )
        == 2
    )

    assert selenium.run_js(
        """
            let finally_occurred = false;
            let c = pyodide._api.pyodide_code.eval_code_async("1+1");
            let result = await c.finally(() => { finally_occurred = true; });
            c.destroy();
            return [result, finally_occurred];
            """
    ) == [2, True]

    assert selenium.run_js(
        """
            let finally_occurred = false;
            let err_occurred = false;
            let c = pyodide._api.pyodide_code.eval_code_async("raise ValueError('hi')");
            try {
                let result = await c.finally(() => { finally_occurred = true; });
            } catch(e){
                err_occurred = e.constructor.name === "PythonError";
            }
            c.destroy();
            return [finally_occurred, err_occurred];
            """
    ) == [True, True]

    assert selenium.run_js(
        """
        let c = pyodide._api.pyodide_code.eval_code_async("raise ValueError('hi')");
        try {
            return await c.catch(e => e.constructor.name === "PythonError");
        } finally {
            c.destroy();
        }
        """
    )

    assert selenium.run_js(
        """
        let c = pyodide._api.pyodide_code.eval_code_async(`
            from js import fetch
            await (await fetch('pyodide-lock.json')).json()
        `);
        let result = await c;
        c.destroy();
        return (!!result) && ("packages" in result);
        """
    )


def test_await_pyproxy_async_def(selenium):
    assert selenium.run_js(
        """
        let packages = await pyodide.runPythonAsync(`
            from js import fetch
            async def temp():
                return await (await fetch('pyodide-lock.json')).json()
            await temp()
        `);
        return (!!packages.packages) && (!!packages.info);
        """
    )


def test_cancellation(selenium):
    @run_in_pyodide
    async def inner(selenium):
        from asyncio import ensure_future, sleep

        from js import fetch

        async def f():
            while True:
                await fetch("/")

        fut = ensure_future(f())
        await sleep(0.01)
        fut.cancel()
        await sleep(0.1)

    inner(selenium)
    assert "InvalidStateError" not in selenium.logs


def test_uncaught_exception(selenium):
    @run_in_pyodide
    async def inner(selenium):
        import asyncio

        async def f():
            1 / 0  # noqa: B018

        asyncio.create_task(f())
        await asyncio.sleep(0)

    inner(selenium)
    expected_message = dedent(
        """\
        Unhandled exception in event loop
        Traceback (most recent call last):

          File "$PYODIDE_ROOT/src/tests/test_asyncio.py", line xxx, in f

        ZeroDivisionError: division by zero
        """
    )

    assert expected_message in re.sub("line [0-9]+", "line xxx", selenium.logs).replace(
        str(PYODIDE_ROOT), "$PYODIDE_ROOT"
    )
