def run_with_resolve(selenium, code):
    selenium.run_js(
        f"""
        try {{
            let promise = new Promise((resolve) => window.resolve = resolve);
            pyodide.runPython({code!r});
            await promise;
        }} finally {{
            delete window.resolve;
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
        """,
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
        """,
    )


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


def test_webloop_exception_handler(selenium):
    selenium.run(
        """
        import asyncio
        async def test():
            raise Exception("test")
        asyncio.ensure_future(test())
        pass
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
