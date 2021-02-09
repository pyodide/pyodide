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
        from js import resolve
        class MyException(Exception):
            pass
        async def foo(arg):
            raise MyException('oops')
        
        def capture_exception(fut):
            try:
                fut.result()
            except MyException:
                resolve()
            else:
                raise Exception("Expected fut.result() to raise MyException")
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
        from js import resolve
        async def dummy_task():
            raise ValueError("oops!")
        async def capture_exception():
            try:
                await dummy_task()
            except ValueError:
                resolve()
            else:
                raise Exception("Expected ValueError")
        import asyncio
        asyncio.ensure_future(capture_exception())
        """,
    )
