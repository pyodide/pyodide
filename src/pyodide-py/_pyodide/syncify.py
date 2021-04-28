from asyncio import Future, ensure_future, iscoroutine
import asyncio
from functools import wraps
import time
from typing import TypeVar, Generic, Generator, List
from warnings import warn

T = TypeVar("T")

SYNC = "sync"
ASYNC = "async"


class AbstractSyncifier:
    """The base class for syncifiers.

    Subclasses should implement syncify_task, which should implement a polling
    loop. The thread needs to ocasionally wake up to handle interrupts. We can
    pass a wake_token to allow the task to signal the polling loop to wake up
    when the task is ready.

    There are three different possible Syncifiers for Pyodide (that I know
    about):
        1. Atomics
        2. Synchronous XHR + service worker
        3. Unthrow (this case will look quite different)

    In the Atomics syncifier, wake_token will be a SharedArrayBuffer and we will
    signal wakeup using Atomics.notify. syncify_task will be implemented in
    Javascript.

    No wake token is needed for Sync XHR because the service worker can send a
    response to the XHR when wakeup is desired.

    Unthrow is completely different: none of this machinery is needed in that
    case because we just get to act like we are inside of an async function even
    when we aren't.
    """

    def syncify(self, t):
        """The main method. Syncify a SyncifyableTask or coroutine."""
        if iscoroutine(t):
            return self.syncify_coroutine(t)
        if isinstance(t, SyncifyableTask):
            t.schedule_sync()
            return self.syncify_task(t)
        raise RuntimeError("Cannot syncify")

    def syncify_coroutine(self, coroutine):
        """Syncify a coroutine by syncifying each future it awaits."""
        try:
            while True:
                fut = coroutine.send(None)
                if not isinstance(fut, SyncifyableTask):
                    raise RuntimeError(
                        "Can only await syncifiables in syncified functions."
                    ) from None
                fut.syncify()
        except StopIteration as e:
            return e.value

    def syncify_task(self, t: "SyncifyableTask[T]") -> T:
        """Poll the task in a loop until it is completed then return the
        result.
        """
        raise NotImplementedError("Subclass me!")

    def getwaketoken(self):
        return None


class TrivialSyncifier(AbstractSyncifier):
    """A trivial reference implementation"""

    def syncify_task(self, t: "SyncifyableTask[T]") -> T:
        while True:
            if t.poll():
                return t.result()
            time.sleep(0.01)


_syncifier = None


def set_syncifier(handler: AbstractSyncifier):
    global _syncifier
    _syncifier = handler


def get_syncifier() -> AbstractSyncifier:
    if _syncifier is None:
        raise RuntimeError("No syncifier")
    return _syncifier


def syncify(func):
    """A decorator for async functions to make them into normal functions."""
    if not callable(func) or isinstance(func, SyncifyableTask):
        return get_syncifier().syncify(func)

    @wraps(func)
    def wrapper(*args):
        return get_syncifier().syncify(func(*args))

    return wrapper


class SyncifyableTaskMeta(type):
    """Override isinstance so we can test JsProxies

    This is easier than figuring out how to make a JsProxy conditionally inherit
    from SyncifyableTask.
    """

    def __instancecheck__(self, x):
        return super().__instancecheck__(x) or callable(
            getattr(x, "schedule_sync", None)
        )


class SyncifyableTask(Future, Generic[T], metaclass=SyncifyableTaskMeta):
    """This is a task that can be scheduled asynchronously or synchronously.

    In general, in order for a Task to be syncifiable, it is necessary that it
    be a request for some other thread to do work so that we can block this
    thread without blocking the work we've requested.

    This is a "task" and not a "future" because it must be scheduled separately
    after creation. This separation between creation and scheduling is necessary
    to allow control over how it is scheduled.
    """

    def __init__(self):
        super().__init__()
        self._mode = None
        self._sync_gen = None
        self.wake_token = None
        self.syncifier = None

    def add_done_callback(self, callback, *, context):
        super().add_done_callback(callback, context=context)
        # When awaited, automatically schedule ourselves asynchronously if we
        # aren't already scheduled.
        if not self._mode:
            self.schedule_async()

    def schedule_async(self):
        """Schedule the task to run asynchronously.

        If you are going to await it immediately, this will happen automatically
        but if you are planning to do other async calls first, you should
        consider explicitly scheduling it so that it can begin work.
        """
        if self._mode == SYNC:
            raise Exception("Already synchronously scheduled")
        if self._mode == ASYNC:
            return
        self._mode = ASYNC
        fut = ensure_future(self.do_async())

        # Attach self to fut
        def wrapper(fut):
            exc = fut.exception()
            if exc:
                self.set_exception(exc)
            else:
                self.set_result(fut.result())

        fut.add_done_callback(wrapper)

    def schedule_sync(self, *, syncifier=None, wake_token=None):
        """Schedule the task to run synchronously."""
        if self._mode == ASYNC:
            raise Exception("Already asynchronously scheduled")
        if self._mode == SYNC:
            return
        self._mode = SYNC
        self.syncifier = syncifier or get_syncifier()
        self.wake_token = wake_token or self.syncifier.getwaketoken()
        self._sync_gen = self.do_sync()
        next(self._sync_gen)

    def poll(self) -> bool:
        """Poll the task for completion.

        Returns True if the task is complete, False if it is not. Even if the
        task isn't done, it may get stuck if this isn't called periodically.
        """
        if self._mode != SYNC:
            raise Exception("Task not synchronously scheduled")
        try:
            next(self._sync_gen)
        except StopIteration as e:
            self.set_result(e.value)
            return True
        except BaseException as e:
            self.set_exception(e)
            return True
        return False

    def syncify(self) -> T:
        """Schedule the task synchronously then block until it is complete."""
        self.schedule_sync()
        return get_syncifier().syncify(self)

    async def do_async(self) -> T:
        """The actual logic to implement this task asynchronously."""
        raise NotImplementedError("do_async should be overriden in a subclass")

    def do_sync(self) -> Generator[None, None, T]:
        """The actual logic to implement this task synchronously.

        Should return generator that yields None until the result is ready, then
        returns it.
        """
        raise NotImplementedError("do_sync should be overriden in a subclass")

    def __del__(self):
        if not self._mode:
            warn("task {self!r} was never scheduled", RuntimeWarning)
        # TODO: Should we invoke self._sync_gen.throw somewhere? Browser docs say that
        # generator finally blocks are not guaranteed to run in general.
        super().__del__()


class SyncifyableGather(SyncifyableTask, Generic[T]):
    """Gather a list of syncifiables into one."""

    def __init__(self, *tasks: List[SyncifyableTask[T]]):
        super().__init__()
        self._tasks = tasks
        self._pending = set(tasks)

    def do_sync(self):
        for task in self._tasks:
            task.schedule_sync(syncifier=self.syncifier, wake_token=self.wake_token)
        while True:
            # TODO: Some way to signal which task woke us up?
            for task in list(self._pending):
                if task.poll():
                    self._pending.remove(task)
            if not self._pending:
                break  # done
            yield  # wait here until we are polled again.

        # Return results from task list
        result = []
        for task in self._tasks:
            res = task.exception()
            if res is None:
                res = task.result()
            result.append(res)
        return result

    def do_async(self):
        return asyncio.gather(*self._tasks)


class ComlinkTask(SyncifyableTask):
    """The main browser implementation of SyncifyableTask.

    Just hands the work to Comlink.
    """

    def __init__(self, proxy):
        super().__init__()
        self.proxy = proxy

    async def do_async(self):
        # Have to be careful here: if we await self.proxy, it will generate an
        # infinite regress.
        return await self.proxy.schedule_sync()

    def do_sync(self):
        return self.proxy.do_sync()


__all__ = ["SyncifyableFuture", "RemoteJsProxyFuture", "syncify"]
