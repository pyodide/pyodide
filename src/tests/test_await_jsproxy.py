import pytest

startup = """
    from asyncio import AbstractEventLoop
    from functools import partial
    class WebLoop(AbstractEventLoop):
        def call_soon(self, coro, arg=None):
            try:
                x = coro.send(arg)
                x = x.then(partial(self.call_soon, coro))
                x.catch(partial(self.fail,coro))
            except StopIteration as result:
                pass

        def fail(self, coro,arg=None):
            pass

    import asyncio
    loop = WebLoop()
    asyncio.set_event_loop(loop)
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
            # TODO: How to assert that x = 10?
            print(x)
        resolve(10)
        loop.call_soon(temp())
        """
    )

def test_await_nonpromise(selenium):
    selenium.run(startup)
    selenium.run(
        """
        from js import Math
        async def temp():
            x = await Math
            print(x)
        loop.call_soon(temp())
        """
    )