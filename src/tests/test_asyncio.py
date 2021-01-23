import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[2] / "src" / "pyodide-py"))

import pytest  # type: ignore
import time


def test_eval_async():
    pass


ASYNCIO_EVENT_LOOP_STARTUP = """
import asyncio
class DumbLoop(asyncio.AbstractEventLoop):
    def create_future(self):
        fut = asyncio.Future(loop=self)
        old_set_result = fut.set_result
        old_set_exception = fut.set_exception
        def set_result(a):
            print("set_result:", a)
            old_set_result(a)
        fut.set_result = set_result
        def set_exception(a):
            print("set_exception:", a)
            old_set_exception(a)
        fut.set_exception = set_exception
        return fut

    def get_debug(self):
        return False

asyncio.set_event_loop(DumbLoop())
"""


def test_await_jsproxy(selenium):
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        def prom(res,rej):
            global resolve
            resolve = res
        from js import Promise
        p = Promise.new(prom)
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


def test_await_fetch(selenium):
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        from js import fetch, window
        async def test():
            response = await fetch("console.html")
            result = await response.text()
            print(result)
            return result
        fetch = fetch.bind(window)

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
            console.log("Hello there???");
            throw new Error("This is an error message!");
        }
        window.async_js_raises = async_js_raises;
        function js_raises(){
            throw new Error("This is an error message!");
        }
        window.js_raises = js_raises;
        """
    )
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        from js import async_js_raises, js_raises
        async def test():
            c = await async_js_raises()
            return c
        c = test()
        r1 = c.send(None)
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


from pyodide._base import eval_code_async


def test_eval_code_async_simple():
    c = eval_code_async("1+92")
    with pytest.raises(StopIteration, match="93"):
        c.send(None)


import asyncio


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
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        def prom(res,rej):
            global resolve
            resolve = res
        from js import Promise
        p = Promise.new(prom)
        from pyodide._base import eval_code_async
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
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        from js import fetch, window
        fetch = fetch.bind(window)
        from pyodide._base import eval_code_async
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
        window.async_js_raises = async_js_raises;
        function js_raises(){
            throw new Error("This is an error message!");
        }
        window.js_raises = js_raises;
        """
    )
    selenium.run(ASYNCIO_EVENT_LOOP_STARTUP)
    selenium.run(
        """
        from js import async_js_raises, js_raises
        from pyodide._base import eval_code_async
        c = eval_code_async(
            '''
            await async_js_raises()
            ''',
            globals=globals()
        )
        r1 = c.send(None)
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


def test_await_pyproxy(selenium):
    assert (
        selenium.run_js(
            """
        let c = pyodide._module.pyodide_py._base.eval_code_async("1+1");
        return await c;
        """
        )
        == 2
    )

    assert (
        selenium.run_js(
            """
        let finally_occurred = false;
        let c = pyodide._module.pyodide_py._base.eval_code_async("1+1");
        let result = await c.finally(() => { finally_occurred = true; });
        return [result, finally_occurred];
        """
        )
        == [2, True]
    )

    assert (
        selenium.run_js(
            """
        let finally_occurred = false;
        let err_occurred = false;
        let c = pyodide._module.pyodide_py._base.eval_code_async("raise ValueError('hi')");
        try {
            let result = await c.finally(() => { finally_occurred = true; });
        } catch(e){
            err_occurred = e.constructor.name === "PythonError";
        }
        return [finally_occurred, err_occurred];
        """
        )
        == [True, True]
    )

    assert selenium.run_js(
        """
        let c = pyodide._module.pyodide_py._base.eval_code_async("raise ValueError('hi')");
        return await c.catch(e => e.constructor.name === "PythonError");
        """
    )

    assert selenium.run_js(
        """
        let packages = await pyodide._module.pyodide_py._base.eval_code_async(`
            from js import fetch
            await (await fetch('packages.json')).json()
        `);
        return (!!packages.dependencies) && (!!packages.import_name_to_package_name);
        """
    )

    assert selenium.run_js(
        """
        let c = pyodide._module.pyodide_py._base.eval_code_async("1+1");
        await c;
        let err_occurred = false;
        try {
            // Triggers: cannot await already awaited coroutine
            await c;
        } catch(e){
            err_occurred = true;
        }
        return err_occurred;
        """
    )
