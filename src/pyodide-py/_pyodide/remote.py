from asyncio import Future, ensure_future, iscoroutine
from functools import wraps


class SyncifyableFuture(Future):
    def add_done_callback(self, callback, *, context):
        fut = ensure_future(self.do_async())

        def wrapper(fut):
            exc = fut.exception()
            if exc:
                self.set_exception(exc)
            else:
                self.set_result(fut.result())
            callback(self)

        fut.add_done_callback(wrapper, context=context)

    async def do_async(self):
        raise NotImplementedError("do_async should be overriden in a subclass")

    def do_sync(self):
        raise NotImplementedError("do_sync should be overriden in a subclass")


class RemoteJsProxyFuture(SyncifyableFuture):
    def __init__(self, proxy):
        super().__init__()
        self.proxy = proxy

    def syncify(self):
        return self.proxy.syncify()

    async def do_async(self):
        return await self.schedule()


class Test:
    def __init__(self, arg):
        self.arg = arg

    def __await__(self):
        return RemoteJsProxyFuture(self.arg).__await__()


async def test():
    return 2


async def test2(r):
    await r


def syncify_coroutine(coroutine):
    try:
        while True:
            fut = coroutine.send(None)
            if not callable(getattr(fut, "syncify", None)):
                raise RuntimeError(
                    "Can't only await syncifiables in syncified functions."
                ) from None
            fut.set_result(fut.syncify())
    except StopIteration as e:
        return e.value


def syncify(func):
    if iscoroutine(func):
        return syncify_coroutine(func)

    @wraps(func)
    def wrapper(*args):
        coroutine = func(*args)
        return syncify_coroutine(coroutine)

    return wrapper
