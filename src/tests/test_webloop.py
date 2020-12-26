from selenium.common.exceptions import TimeoutException


class TaskDone:
    def __call__(self, driver):
        done = driver.execute_script("return window.task_done")
        return bool(done)


def test_webloop(selenium):
    selenium.run(loop_script)

    # test asyncio.sleep
    selenium.run(
        """
        import js
        import asyncio
        from pyodide import WebLoop, WebLoopPolicy
        asyncio.set_event_loop_policy(WebLoopPolicy())
        loop = asyncio.get_event_loop()
        assert isinstance(loop, WebLoop)

        js.window.task_done = False
        async def sleep_task():
            print('start sleeping for 1s')
            await asyncio.sleep(0.1)
            print('sleeping done')
            js.window.task_done = True

        loop.run_until_complete(sleep_task())
        """
    )

    try:
        selenium.wait.until(TaskDone())
    except TimeoutException:
        raise TimeoutException("asyncio.sleep timed out")

    # test await wrapped js promise
    selenium.run(
        """
        loop.run_forever()

        js.eval('''
        async function asyncFetch(url){
        const response = await fetch(url)
        const data = await response.text()
        return data
        }
        ''')

        def wrap_promise(promise):
            loop = asyncio.get_event_loop()
            fut = loop.create_future()
            def set_exception(e):
                fut.set_exception(Exception(str(e)))
            promise.then(fut.set_result).catch(set_exception)
            return fut

        js.window.task_done = False
        async def fetch_task():
            print('fetching data...')
            promise = js.asyncFetch('console.html')
            result = await wrap_promise(promise)
            print('finished: ', result)
            js.window.task_done = True

        asyncio.ensure_future(fetch_task())
        """
    )
    try:
        selenium.wait.until(TaskDone())
    except TimeoutException:
        raise TimeoutException("fetching promise task timed out")

    # test asyncio exception
    selenium.run(
        """
        class MyCustomException(Exception):
            pass

        async def dummy_task():
            raise MyCustomException("oops!")

        js.window.task_done = False
        async def capture_exception():
            try:
                await dummy_task()
            except MyCustomException as e:
                js.window.task_done = True

        asyncio.ensure_future(capture_exception())
        """
    )
    try:
        selenium.wait.until(TaskDone())
    except TimeoutException:
        raise TimeoutException("catching asyncio exception timed out")

    # test custom exception hanlder
    selenium.run(
        """
        class MyCustomException(Exception):
            pass

        async def dummy_task():
            raise MyCustomException("oops!")

        js.window.task_done = False
        def exception_handler(loop, context):
            exception = context.get("exception", None)
            print("exception_handler:", exception)
            if isinstance(exception, MyCustomException):
                js.window.task_done = True

        loop.set_exception_handler(exception_handler)
        asyncio.ensure_future(dummy_task())
        """
    )

    try:
        selenium.wait.until(TaskDone())
    except TimeoutException:
        raise TimeoutException("catching exception with custom handler timed out")
