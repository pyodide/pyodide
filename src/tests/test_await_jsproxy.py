from selenium.common.exceptions import WebDriverException
import pytest
import time

startup = """
import asyncio
class DumbLoop(asyncio.AbstractEventLoop):
    def create_future(self):
        return asyncio.Future(loop=self)

    def get_debug(self):
        return False

asyncio.set_event_loop(DumbLoop())
"""


def test_await_jsproxy(selenium):
    selenium.run(startup)
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
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            c.send(r.result())
            """
        )


def test_await_fetch(selenium):
    selenium.run(startup)
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
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            c.send(r2.result())
            """
        )


def test_await_nonpromise(selenium):
    msg = "TypeError: Attempted to await .* which is not a promise."
    with pytest.raises(WebDriverException, match=msg):
        selenium.run(
            """
            from js import Math
            async def temp():
                x = await Math
                print(x)
            c = temp()
            c.send(None)
            """
        )
