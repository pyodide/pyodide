import asyncio
import time
import contextvars


from typing import Callable


class WebLoop(asyncio.AbstractEventLoop):
    """A custom event loop for use in Pyodide.

    Schedules tasks on the browser event loop. Does no lifecycle management and runs
    forever.

    ``run_forever`` and ``run_until_complete`` cannot block like a normal event loop would
    because we only have one thread so blocking would stall the browser event loop
    and prevent anything from ever happening.

    We defer all work to the browser event loop using the setTimeout function.
    To ensure that this event loop doesn't stall out UI and other browser handling,
    we want to make sure that each task is scheduled on the browser event loop as a
    task not as a microtask. ``setTimeout(callback, 0)`` enqueues the callback as a
    task so it works well for our purposes.
    """

    def __init__(self):
        self._task_factory = None
        asyncio._set_running_loop(self)

    def get_debug(self):
        return False

    #
    # Lifecycle methods: We ignore all lifecycle management
    #

    def is_running(self) -> bool:
        """Returns ``True`` if the event loop is running.

        Always returns ``True`` because WebLoop has no lifecycle management.
        """
        return True

    def is_closed(self) -> bool:
        """Returns ``True`` if the event loop was closed.

        Always returns ``False`` because WebLoop has no lifecycle management.
        """
        return False

    def _check_closed(self):
        """Used in create_task.

        Would raise an error if ``self.is_closed()``, but we are skipping all lifecycle stuff.
        """
        pass

    def run_forever(self):
        """Run the event loop forever. Does nothing in this implementation.

        We cannot block like a normal event loop would
        because we only have one thread so blocking would stall the browser event loop
        and prevent anything from ever happening.
        """
        pass

    def run_until_complete(self, future):
        """Run until future is done.

        If the argument is a coroutine, it is wrapped in a Task.

        The native event loop `run_until_complete` blocks until evaluation of the
        future is complete and then returns the result of the future.
        Since we cannot block, we just ensure that the future is scheduled and
        return the future. This makes this method a bit useless. Instead, use
        `future.add_done_callback(do_something_with_result)` or:
        ```python
        async def wrapper():
            result = await future
            do_something_with_result(result)
        ```
        """
        return asyncio.ensure_future(future)

    #
    # Scheduling methods: use browser.setTimeout to schedule tasks on the browser event loop.
    #

    def call_soon(self, callback: Callable, *args, context: contextvars.Context = None):
        """Arrange for a callback to be called as soon as possible.

        Any positional arguments after the callback will be passed to
        the callback when it is called.

        This schedules the callback on the browser event loop using ``setTimeout(callback, 0)``.
        """
        delay = 0
        return self.call_later(delay, callback, *args, context=context)

    def call_soon_threadsafe(
        self, callback: Callable, *args, context: contextvars.Context = None
    ):
        """Like ``call_soon()``, but thread-safe.

        We have no threads so everything is "thread safe", and we just use ``call_soon``.
        """
        return self.call_soon(callback, *args, context=context)

    def call_later(
        self,
        delay: float,
        callback: Callable,
        *args,
        context: contextvars.Context = None
    ):
        """Arrange for a callback to be called at a given time.

        Return a Handle: an opaque object with a cancel() method that
        can be used to cancel the call.

        The delay can be an int or float, expressed in seconds.  It is
        always relative to the current time.

        Each callback will be called exactly once.  If two callbacks
        are scheduled for exactly the same time, it undefined which
        will be called first.

        Any positional arguments after the callback will be passed to
        the callback when it is called.

        This uses `setTimeout(callback, delay)`
        """
        from js import setTimeout
        from . import create_once_callable

        if delay < 0:
            raise ValueError("Can't schedule in the past")
        h = asyncio.Handle(callback, args, self, context=context)  # type: ignore
        setTimeout(create_once_callable(h._run), delay * 1000)
        return h

    def call_at(
        self,
        when: float,
        callback: Callable,
        *args,
        context: contextvars.Context = None
    ):
        """Like ``call_later()``, but uses an absolute time.

        Absolute time corresponds to the event loop's ``time()`` method.

        This uses ``setTimeout(callback, when - cur_time)``
        """
        cur_time = self.time()
        delay = when - cur_time
        return self.call_later(delay, callback, *args, context=context)

    def run_in_executor(self, executor, func, *args):
        """Arrange for func to be called in the specified executor.

        This is normally supposed to run func(*args) in a separate process or
        thread and signal back to our event loop when it is done. It's possible
        to make the executor, but if we actually try to submit any functions to
        it, it will try to create a thread and throw an error. Best we can do is
        to run func(args) in this thread and stick the result into a future.
        """
        fut = self.create_future()
        try:
            fut.set_result(func(*args))
        except BaseException as e:
            fut.set_exception(e)
        return fut

    #
    # The remaining methods are copied directly from BaseEventLoop
    #

    def time(self):
        """Return the time according to the event loop's clock.

        This is a float expressed in seconds since an epoch, but the
        epoch, precision, accuracy and drift are unspecified and may
        differ per event loop.

        Copied from ``BaseEventLoop.time``
        """
        return time.monotonic()

    def create_future(self):
        """Create a Future object attached to the loop.

        Copied from ``BaseEventLoop.create_future``
        """
        return asyncio.futures.Future(loop=self)

    def create_task(self, coro, *, name=None):
        """Schedule a coroutine object.

        Return a task object.

        Copied from ``BaseEventLoop.create_task``
        """
        self._check_closed()
        if self._task_factory is None:
            task = asyncio.tasks.Task(coro, loop=self, name=name)
            if task._source_traceback:
                # Added comment:
                # this only happens if get_debug() returns True.
                # In that case, remove create_task from _source_traceback.
                del task._source_traceback[-1]
        else:
            task = self._task_factory(self, coro)
            asyncio.tasks._set_task_name(task, name)

        return task

    def set_task_factory(self, factory):
        """Set a task factory that will be used by loop.create_task().

        If factory is None the default task factory will be set.

        If factory is a callable, it should have a signature matching
        '(loop, coro)', where 'loop' will be a reference to the active
        event loop, 'coro' will be a coroutine object.  The callable
        must return a Future.

        Copied from ``BaseEventLoop.set_task_factory``
        """
        if factory is not None and not callable(factory):
            raise TypeError("task factory must be a callable or None")
        self._task_factory = factory

    def get_task_factory(self):
        """Return a task factory, or None if the default one is in use.

        Copied from ``BaseEventLoop.get_task_factory``
        """
        return self._task_factory


class WebLoopPolicy(asyncio.DefaultEventLoopPolicy):  # type: ignore
    """
    A simple event loop policy for managing WebLoop based event loops.
    """

    def __init__(self):
        self._default_loop = None

    def get_event_loop(self):
        """Get the current event loop"""
        if self._default_loop:
            return self._default_loop
        return self.new_event_loop()

    def new_event_loop(self):
        """Create a new event loop"""
        self._default_loop = WebLoop()
        return self._default_loop

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the current event loop"""
        self._default_loop = loop
