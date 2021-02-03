import asyncio
from asyncio import tasks, futures
import time
import contextvars


from typing import Awaitable, Callable


class WebLoop(asyncio.AbstractEventLoop):
    """A custom event loop for use in Pyodide.

    Does no lifecycle management and runs forever (it is just deferring work to the
    browser event loop which has no lifecycle so why should we have one?)

    run_forever and run_until_complete cannot block like a normal event loop would
    because we only have one thread so blocking would stall the browser event loop
    and prevent anything from ever happening.

    We defer all work to the browser event loop using the setTimeout function.
    To ensure that this event loop doesn't stall out UI and other browser handling,
    we want to make sure that each task is scheduled on the browser event loop as a
    task not as a microtask. `setTimeout(callback, 0)` enqueues the callback as a
    task so it works well for our purposes.
    """

    def __init__(self, debug: bool = False, interval: int = 10):
        self._task_factory = None
        asyncio._set_running_loop(self)

    def get_debug(self):
        return False

    #
    # Lifecycle methods: We ignore all lifecycle management
    #

    def is_running(self) -> bool:
        return True

    def is_closed(self) -> bool:
        return False

    def _check_closed(self):
        """ Used in create_task. Would raise an error if self.is_closed(), but we are skipping all lifecycle stuff. """
        pass

    def run_forever(self):
        """We cannot block like a normal event loop would
        because we only have one thread so blocking would stall the browser event loop
        and prevent anything from ever happening.
        """
        pass

    def run_until_complete(self, future: Awaitable):
        """ Since we cannot block, we just ensure that the future is scheduled. """
        return asyncio.ensure_future(future)

    #
    # Scheduling methods: use browser.setTimeout to schedule tasks on the browser event loop.
    #

    def call_soon(self, callback: Callable, *args, context: contextvars.Context = None):
        """
        Schedule the callback callback to be called with args arguments at the next iteration of the event loop.
        """
        delay = 0
        return self.call_later(delay, callback, *args, context=context)

    def call_soon_threadsafe(
        callback: Callable, *args, context: contextvars.Context = None
    ):
        """
        A thread-safe variant of call_soon().

        Note this function is different from the standard asyncio loop implementation, it is current exactly the same as call_soon
        """
        return self.call_soon(callback, *args, context=context)

    def call_later(
        self,
        delay: float,
        callback: Callable,
        *args,
        context: contextvars.Context = None
    ):
        """
        Schedule callback to be called after the given delay number of seconds (can be either an int or a float).
        """
        from js import setTimeout

        if delay < 0:
            raise Exception("Can't schedule in the past")
        h = asyncio.Handle(callback, args, self, context=context)
        setTimeout(h._run, delay * 1000)
        return h

    def call_at(
        self,
        when: float,
        callback: Callable,
        *args,
        context: contextvars.Context = None
    ):
        """
        Schedule callback to be called at the given absolute timestamp when (an int or a float), using the same time reference as loop.time().
        """
        cur_time = self.time()
        delay = when - cur_time
        return self.call_later(delay, callback, *args, context=context)

    #
    # The remaining methods are copied directly from BaseEventLoop
    #

    def time(self):
        """Return the time according to the event loop's clock.

        This is a float expressed in seconds since an epoch, but the
        epoch, precision, accuracy and drift are unspecified and may
        differ per event loop.

        Copied from BaseEventLoop.time
        """
        return time.monotonic()

    def create_future(self):
        """Create a Future object attached to the loop.

        Copied from BaseEventLoop.create_future
        """
        return futures.Future(loop=self)

    def create_task(self, coro, *, name=None):
        """Schedule a coroutine object.

        Return a task object.

        Copied from BaseEventLoop.create_task
        """
        self._check_closed()
        if self._task_factory is None:
            task = tasks.Task(coro, loop=self, name=name)
            if task._source_traceback:
                del task._source_traceback[-1]
        else:
            task = self._task_factory(self, coro)
            tasks._set_task_name(task, name)

        return task

    def set_task_factory(self, factory):
        """Set a task factory that will be used by loop.create_task().

        If factory is None the default task factory will be set.

        If factory is a callable, it should have a signature matching
        '(loop, coro)', where 'loop' will be a reference to the active
        event loop, 'coro' will be a coroutine object.  The callable
        must return a Future.

        Copied from BaseEventLoop.set_task_factory
        """
        if factory is not None and not callable(factory):
            raise TypeError("task factory must be a callable or None")
        self._task_factory = factory

    def get_task_factory(self):
        """Return a task factory, or None if the default one is in use.

        Copied from BaseEventLoop.get_task_factory
        """
        return self._task_factory


class SimpleWebLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """
    A simple event loop policy for managing WebLoop based event loops.
    """

    def __init__(self):
        self._default_loop = None

    def get_event_loop(self):
        """
        Get the current event loop
        """
        if self._default_loop is None:
            self._default_loop = SimpleWebLoop()
        return self._default_loop

    def new_event_loop(self):
        """
        Create a new event loop
        """
        self._default_loop = SimpleWebLoop()
        return self._default_loop

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Set the current event loop
        """
        self._default_loop = loop
