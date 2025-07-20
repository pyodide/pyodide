import pytest
from pytest_pyodide.decorator import run_in_pyodide


def run_with_resolve(selenium, code):
    selenium.run_js(
        f"""
        try {{
            let promise = new Promise((resolve) => self.resolve = resolve);
            pyodide.runPython({code!r});
            await promise;
        }} finally {{
            delete self.resolve;
        }}
        """
    )


def test_asyncio_sleep(selenium):
    # test asyncio.sleep
    run_with_resolve(
        selenium,
        """
        import asyncio
        from js import resolve
        async def sleep_task():
            print('start sleeping for 1s')
            await asyncio.sleep(1)
            print('sleeping done')
            resolve()
        asyncio.ensure_future(sleep_task())
        None
        """,
    )


def test_cancel_handle(selenium_standalone):
    selenium_standalone.run_js(
        """
        await pyodide.runPythonAsync(`
            import asyncio
            loop = asyncio.get_event_loop()
            exc = []
            def exception_handler(loop, context):
                exc.append(context)
            loop.set_exception_handler(exception_handler)
            try:
                await asyncio.wait_for(asyncio.sleep(1), 2)
            finally:
                loop.set_exception_handler(None)
            assert not exc
        `);
        """
    )


def test_cancel_unhandled(selenium):
    selenium.run_async(
        """
        import asyncio
        loop = asyncio.get_running_loop()

        async def f():
            await asyncio.sleep(1)

        t = loop.create_task(f())
        print("done:", t.done())
        print("cancel:", t.cancel())
        await asyncio.sleep(2)
        """
    )


def test_return_result(selenium):
    # test return result
    run_with_resolve(
        selenium,
        """
        from js import resolve
        async def foo(arg):
            return arg

        def check_result(fut):
            result = fut.result()
            if result == 998:
                resolve()
            else:
                raise Exception(f"Unexpected result {result!r}")
        import asyncio
        fut = asyncio.ensure_future(foo(998))
        fut.add_done_callback(check_result)

        """,
    )


def test_capture_exception(selenium):
    run_with_resolve(
        selenium,
        """
        from unittest import TestCase
        raises = TestCase().assertRaises
        from js import resolve
        class MyException(Exception):
            pass
        async def foo(arg):
            raise MyException('oops')

        def capture_exception(fut):
            with raises(MyException):
                fut.result()
            resolve()
        import asyncio
        fut = asyncio.ensure_future(foo(998))
        fut.add_done_callback(capture_exception)
        """,
    )


def test_await_js_promise(selenium):
    run_with_resolve(
        selenium,
        """
        from js import fetch, resolve
        async def fetch_task():
            print('fetching data...')
            result = await fetch('console.html')
            resolve()
        import asyncio
        asyncio.ensure_future(fetch_task())
        None
        """,
    )


def test_call_soon(selenium):
    run_with_resolve(
        selenium,
        """
        from js import resolve
        def foo(arg):
            if arg == 'bar':
                resolve()
            else:
                raise Exception("Expected arg == 'bar'...")
        import asyncio
        asyncio.get_event_loop().call_soon(foo, 'bar')
        None
        """,
    )


def test_contextvars(selenium):
    run_with_resolve(
        selenium,
        """
        from js import resolve
        import contextvars
        request_id = contextvars.ContextVar('Id of request.')
        request_id.set(123)
        ctx = contextvars.copy_context()
        request_id.set(456)
        def func_ctx():
            if request_id.get() == 123:
                resolve()
            else:
                raise Exception(f"Expected request_id.get() == '123', got {request_id.get()!r}")
        import asyncio
        asyncio.get_event_loop().call_soon(func_ctx, context=ctx)
        None
        """,
    )


def test_asyncio_exception(selenium):
    run_with_resolve(
        selenium,
        """
        from unittest import TestCase
        raises = TestCase().assertRaises
        from js import resolve
        async def dummy_task():
            raise ValueError("oops!")
        async def capture_exception():
            with raises(ValueError):
                await dummy_task()
            resolve()
        import asyncio
        asyncio.ensure_future(capture_exception())
        None
        """,
    )


@pytest.mark.skip_pyproxy_check
def test_run_in_executor(selenium):
    # If run_in_executor tries to actually use ThreadPoolExecutor, it will throw
    # an error since we can't start threads
    selenium.run_js(
        """
        pyodide.runPythonAsync(`
            from concurrent.futures import ThreadPoolExecutor
            import asyncio
            def f():
                return 5
            result = await asyncio.get_event_loop().run_in_executor(ThreadPoolExecutor(), f)
            assert result == 5
        `);
        """
    )


@pytest.mark.xfail(reason="Works locally but failing in test suite as of #2022.")
def test_webloop_exception_handler(selenium_standalone):
    selenium = selenium_standalone
    selenium.run_async(
        """
        import asyncio
        async def test():
            raise Exception("test")
        asyncio.ensure_future(test())
        await asyncio.sleep(0.2)
        """
    )
    assert "Task exception was never retrieved" in selenium.logs
    try:
        selenium.run_js(
            """
            pyodide.runPython(`
                import asyncio
                loop = asyncio.get_event_loop()
                exc = []
                def exception_handler(loop, context):
                    exc.append(context)
                loop.set_exception_handler(exception_handler)

                async def test():
                    raise Exception("blah")
                asyncio.ensure_future(test());
                1
            `);
            await sleep(100)
            pyodide.runPython(`
                assert exc[0]["exception"].args[0] == "blah"
            `)
            """
        )
    finally:
        selenium.run("loop.set_exception_handler(None)")


@pytest.mark.asyncio
async def test_pyodide_future():
    import asyncio

    from pyodide.webloop import PyodideFuture

    fut: PyodideFuture[int]

    fut = PyodideFuture()
    increment = lambda x: x + 1
    tostring = lambda x: repr(x)

    def raises(x):
        raise Exception(x)

    rf = fut.then(increment).then(increment)
    fut.set_result(5)
    assert await rf == 7

    e = Exception("oops")
    fut = PyodideFuture()
    rf = fut.then(increment, tostring)
    fut.set_exception(e)
    assert await rf == repr(e)

    e = Exception("oops")
    fut = PyodideFuture()
    rf = fut.catch(tostring)
    fut.set_exception(e)
    assert await rf == repr(e)

    async def f(x):
        await asyncio.sleep(0.1)
        return x + 1

    fut = PyodideFuture()
    rf = fut.then(f)

    fut.set_result(6)
    assert await rf == 7

    fut = PyodideFuture()
    rf = fut.then(raises)
    fut.set_result(6)
    try:
        await rf
    except Exception:
        pass
    assert repr(rf.exception()) == repr(Exception(6))

    x = 0

    def incx():
        nonlocal x
        x += 1

    fut = PyodideFuture()
    rf = fut.then(increment).then(increment).finally_(incx).finally_(incx)
    assert x == 0
    fut.set_result(5)
    await rf
    assert x == 2

    fut = PyodideFuture()
    rf = fut.then(increment).then(increment).finally_(incx).finally_(incx)
    fut.set_exception(e)
    try:
        await rf
    except Exception:
        pass
    assert x == 4

    async def f1(x):
        if x == 0:
            return 7
        await asyncio.sleep(0.1)
        return f1(x - 1)

    fut = PyodideFuture()
    rf = fut.then(f1)
    fut.set_result(3)
    assert await rf == 7

    async def f2():
        await asyncio.sleep(0.1)
        raise e

    fut = PyodideFuture()
    rf = fut.finally_(f2)
    fut.set_result(3)
    try:
        await rf
    except Exception:
        pass
    assert rf.exception() == e

    fut = PyodideFuture()
    rf = fut.finally_(f2)
    fut.set_exception(Exception("oops!"))
    try:
        await rf
    except Exception:
        pass
    assert rf.exception() == e


@run_in_pyodide
async def test_pyodide_future2(selenium):
    from js import fetch
    from pyodide.ffi import JsFetchResponse, JsProxy

    async def get_json(x: JsFetchResponse) -> JsProxy:
        return await x.json()

    def get_name(x: JsProxy) -> str:
        return x.info.name  # type:ignore[attr-defined]

    url = "https://pypi.org/pypi/pytest/json"
    b = fetch(url).then(get_json)
    name = await b.then(get_name)
    assert name == "pytest"


@run_in_pyodide
async def test_pyodide_task(selenium):
    from asyncio import Future, ensure_future, sleep

    async def taskify(fut):
        return await fut

    def do_the_thing():
        d = dict(
            did_onresolve=None,
            did_onreject=None,
            did_onfinally=False,
        )
        f: Future[int] = Future()
        t = ensure_future(taskify(f))
        t.then(
            lambda v: d.update(did_onresolve=v), lambda e: d.update(did_onreject=e)
        ).finally_(lambda: d.update(did_onfinally=True))
        return f, d

    f, d = do_the_thing()
    f.set_result(7)
    await sleep(0.1)
    assert d == dict(
        did_onresolve=7,
        did_onreject=None,
        did_onfinally=True,
    )

    f, d = do_the_thing()
    e = Exception("Oops!")
    f.set_exception(e)
    assert d == dict(
        did_onresolve=None,
        did_onreject=None,
        did_onfinally=False,
    )
    await sleep(0.1)
    assert d == dict(
        did_onresolve=None,
        did_onreject=e,
        did_onfinally=True,
    )


@run_in_pyodide
async def test_inprogress(selenium):
    import asyncio

    from pyodide.webloop import WebLoop

    loop: WebLoop = asyncio.get_event_loop()  # type: ignore[assignment]
    loop._in_progress = 0

    ran_no_in_progress_handler = False

    def _no_in_progress_handler():
        nonlocal ran_no_in_progress_handler
        ran_no_in_progress_handler = True

    ran_keyboard_interrupt_handler = False

    def _keyboard_interrupt_handler():
        print("_keyboard_interrupt_handler")
        nonlocal ran_keyboard_interrupt_handler
        ran_keyboard_interrupt_handler = True

    system_exit_code = None

    def _system_exit_handler(exit_code):
        nonlocal system_exit_code
        system_exit_code = exit_code

    try:
        loop._no_in_progress_handler = _no_in_progress_handler
        loop._keyboard_interrupt_handler = _keyboard_interrupt_handler
        loop._system_exit_handler = _system_exit_handler

        fut = loop.create_future()

        async def temp():
            await fut

        fut2 = asyncio.ensure_future(temp())
        await asyncio.sleep(0)
        assert loop._in_progress == 2
        fut.set_result(0)
        await fut2

        assert loop._in_progress == 0
        assert ran_no_in_progress_handler
        assert not ran_keyboard_interrupt_handler
        assert not system_exit_code

        ran_no_in_progress_handler = False

        fut = loop.create_future()

        async def temp():
            await fut

        fut2 = asyncio.ensure_future(temp())
        assert loop._in_progress == 2
        fut.set_exception(KeyboardInterrupt())
        try:
            await fut2
        except KeyboardInterrupt:
            pass

        assert loop._in_progress == 0
        assert ran_no_in_progress_handler
        assert ran_keyboard_interrupt_handler
        assert not system_exit_code  # type: ignore[unreachable]

        ran_no_in_progress_handler = False
        ran_keyboard_interrupt_handler = False

        fut = loop.create_future()

        async def temp():
            await fut

        fut2 = asyncio.ensure_future(temp())
        assert loop._in_progress == 2
        fut.set_exception(SystemExit(2))
        try:
            await fut2
        except SystemExit:
            pass
        assert loop._in_progress == 0
        assert ran_no_in_progress_handler
        assert not ran_keyboard_interrupt_handler
        assert system_exit_code == 2

        ran_no_in_progress_handler = False
        system_exit_code = None

    finally:
        loop._in_progress = 1
        loop._no_in_progress_handler = None
        loop._keyboard_interrupt_handler = None
        loop._system_exit_handler = None


@run_in_pyodide
async def test_zero_timeout(selenium):
    import asyncio
    import time

    now = time.time()

    for _ in range(1000):
        await asyncio.sleep(0)

    done = time.time()
    elapsed = done - now

    # Very rough check, we hope it's less than 4s (1000 * 4ms [setTimeout delay in most browsers])
    assert elapsed < 4, f"elapsed: {elapsed}s"


@run_in_pyodide
async def test_create_task_context(selenium):
    import asyncio as aio
    from contextvars import ContextVar, copy_context

    cvar = ContextVar("test_create_task_context", default=0)
    cvar.set(1)
    ctx_with_1 = copy_context()
    cvar.set(2)

    async def get_cvar() -> int:
        return cvar.get()

    assert await get_cvar() == 2  # Sanity check

    task = aio.create_task(get_cvar(), context=ctx_with_1)
    assert await task == 1
