#! /usr/bin/env python
# -*- coding: utf-8 -*-
# flake8: noqa

"""

A custom event loop for running asyncio in Pyodide

Version: 0.1.2

Author: Wei OUYANG (@oeway)
        Adapted from the EventSimulator made by @damonjw
        https://gist.github.com/damonjw/35aac361ca5d313ee9bf79e00261f4ea

Version History:
        * support contextvars
        * add event loop policy
        * throw error when the loop is already running
        * support Python 3.8
        * fix run_until_complete
"""

import heapq
import asyncio
import time
import traceback
import contextvars

import js
from typing import Dict, Tuple, Optional, Awaitable, Callable


class WebLoop(asyncio.AbstractEventLoop):
    """A custom event loop for running asyncio in Pyodide

    It works by utilizing the browser event loop via the setTimeout function
    """

    def __init__(self, debug: Optional[bool] = False, interval: Optional[int] = 10):
        """
        Instatiate the web loop
        """
        self._running = False
        self._immediate = []
        self._scheduled = []
        self._futures = []
        self._next_handle = None
        self._debug = debug
        self._stop = False
        self._interval = interval
        self._timeout_promise = js.eval(
            "self._timeoutPromise = function(time){return new Promise((resolve)=>{setTimeout(resolve, time);});}"
        )
        self._exception_handler = None
        self._task_factory = self._default_task_factory
        self._stop_callbacks = None
        self._result = None
        self._exception = None

    def get_debug(self):
        """
        Get the debug mode (bool) of the event loop.
        """
        return self._debug

    def set_debug(self, enabled: bool):
        """
        Set the debug mode of the event loop.
        """
        self._debug = enabled

    def time(self):
        """
        Return the current time, as a float value, according to the time module (time.time()).
        """
        return time.time()

    def run_forever(self):
        """
        Run the event loop until stop() is called.

        Note that this function is different from the standard asyncio loop implementation in two ways:
         1) It won't block the execution
         2) It returns a Promise object that will be resolved when loop.stop() or loop.close() is called

        """
        if self._running:
            raise RuntimeError("This event loop is already running")

        def run(resolve, reject):
            self._stop = False
            if asyncio.get_event_loop() == self:
                asyncio._set_running_loop(self)
            self._stop_callbacks = (resolve, reject)
            self._do_tasks(forever=True)

        return js.Promise.new(run)

    def run_until_complete(self, future: Awaitable):
        """
        Run until the future (an instance of Future) has completed.

        Note that this function is different from the standard asyncio loop implementation in two ways:
         1) It won't block the execution
         2) It returns a Promise object that can be resolved into the result of the future object or raise an exception

        Parameters
        ----------
        future
        A future or coroutine object


        Returns
        -------
        A Promise object with the returned result or exception
        """
        if self._running:
            raise RuntimeError("This event loop is already running")

        def run(resolve, reject):
            asyncio.ensure_future(future)
            if asyncio.get_event_loop() == self:
                asyncio._set_running_loop(self)
            self._stop = False
            self._stop_callbacks = (resolve, reject)
            self._do_tasks(until_complete=True)

        return js.Promise.new(run)

    def _do_tasks(
        self,
        until_complete: Optional[bool] = False,
        forever: Optional[bool] = False,
    ):
        """
        Do the tasks
        """
        self._exception = None
        self._result = None
        self._running = True
        if self._stop:
            self._quit_running()
            return
        while len(self._immediate) > 0:
            h = self._immediate[0]
            self._immediate = self._immediate[1:]
            if not h._cancelled:
                h._run()
            if self._stop:
                self._quit_running()
                return

        if self._next_handle is not None:
            if self._next_handle._cancelled:
                self._next_handle = None

        if self._scheduled and self._next_handle is None:
            h = heapq.heappop(self._scheduled)
            h._scheduled = True
            self._next_handle = h

        if self._next_handle is not None and self._next_handle._when <= self.time():
            h = self._next_handle
            self._next_handle = None
            self._immediate.append(h)

        not_finished = (
            self._immediate or self._scheduled or self._next_handle or self._futures
        )
        if forever or (until_complete and not_finished):
            self._timeout_promise(self._interval).then(
                lambda x: self._do_tasks(until_complete=until_complete, forever=forever)
            )
        else:
            self._quit_running()

    def _quit_running(self):
        """
        Quit running
        """
        if asyncio.get_event_loop() == self:
            asyncio._set_running_loop(None)
        self._running = False
        if self._stop_callbacks:
            resolve, reject = self._stop_callbacks
            self._stop_callbacks = None
            if self._exception:
                reject(self._exception)
            else:
                resolve(self._result)

    def _timer_handle_cancelled(self, handle: Callable):
        """
        Timer handle canlled
        """
        pass

    def is_running(self) -> bool:
        """
        Return True if the event loop is currently running.
        """
        return self._running

    def is_closed(self) -> bool:
        """
        Return True if the event loop was closed.
        """
        return not self._running

    def stop(self):
        """
        Stop the event loop.
        """
        self._stop = True
        self._quit_running()

    def close(self):
        """
        Close the event loop.
        """
        self._stop = True
        self._quit_running()

    def shutdown_asyncgens(self):
        raise NotImplementedError

    def shutdown_default_executor(self):
        raise NotImplementedError

    def default_exception_handler(self, context: Dict) -> Callable:
        """
        Default exception handler.
        """
        js.console.error(context.get("message"))

    def call_exception_handler(self, context: Dict):
        """
        Call the current event loop exception handler.

        Parameters
        ----------
        context
          context is a dict object containing the following keys (new keys may be introduced in future Python versions):
            ‘message’: Error message;
            ‘exception’ (optional): Exception object;
            ‘future’ (optional): asyncio.Future instance;
            ‘handle’ (optional): asyncio.Handle instance;
            ‘protocol’ (optional): Protocol instance;
            ‘transport’ (optional): Transport instance;
            ‘socket’ (optional): socket.socket instance.
        """
        # note that custom exception handler has different signature compared to default_exception_handler
        if self._exception_handler:
            self._exception_handler(self, context)
        else:
            self.default_exception_handler(context)

    def set_exception_handler(self, handler: Optional[Callable]):
        """
        Set handler as the new event loop exception handler.
        Parameters
        ----------
        handler
          If handler is None, the default exception handler will be set.
        Otherwise, handler must be a callable with the signature matching (loop, context),
        where loop is a reference to the active event loop, and context is a dict object
        containing the details of the exception (see call_exception_handler() documentation
        for details about context).
        """
        if handler == self.default_exception_handler:
            self._exception_handler = None
        else:
            self._exception_handler = handler

    def get_exception_handler(self):
        """
        Return the current exception handler, or None if no custom exception handler was set.
        """
        return self._exception_handler

    def call_soon(self, callback: Callable, *args, context: contextvars.Context = None):
        """
        Schedule the callback callback to be called with args arguments at the next iteration of the event loop.
        """
        h = asyncio.Handle(callback, args, self, context=context)
        self._immediate.append(h)
        return h

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
        if delay < 0:
            raise Exception("Can't schedule in the past")
        return self.call_at(self.time() + delay, callback, *args, context=context)

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
        if when < self.time():
            raise Exception("Can't schedule in the past")
        h = asyncio.TimerHandle(when, callback, args, self, context=context)
        heapq.heappush(self._scheduled, h)
        h._scheduled = True
        return h

    def create_task(self, coro: Awaitable, name: Optional[str] = None) -> asyncio.Task:
        """
        Schedule the execution of a Coroutines. Return a Task object.
        """
        return self._task_factory(self, coro, name=name)

    def _default_task_factory(
        self,
        loop: asyncio.AbstractEventLoop,
        coro: Awaitable,
        name: Optional[str] = None,
    ):
        """
        The default task factory
        """

        async def wrapper():
            try:
                self._result = await coro
            except Exception as e:
                self._exception = e
                self.call_exception_handler(
                    {"message": traceback.format_exc(), "exception": e}
                )

        return asyncio.Task(wrapper(), loop=self, name=name)

    def create_future(self):
        """
        Create an asyncio.Future object attached to the event loop.
        """
        fut = asyncio.Future(loop=self)

        def remove_fut(*args):
            self._futures.remove(fut)

        fut.add_done_callback(remove_fut)
        self._futures.append(fut)
        return fut

    def set_task_factory(self, factory: Callable):
        """
        Set the task factory
        """
        self._task_factory = factory

    def get_task_factory(
        self,
    ):
        """
        Return a task factory or None if the default one is in use.
        """
        if self._task_factory == self._default_task_factory:
            return None
        return self._task_factory


class WebLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """
    A simple event loop policy for managing WebLoop based event loops.
    """

    def __init__(self):
        """
        Instantiate the web loop policy
        """
        self._default_loop = None

    def get_event_loop(self):
        """
        Get the current event loop
        """
        if self._default_loop is None:
            self._default_loop = WebLoop()
        return self._default_loop

    def new_event_loop(self):
        """
        Create a new event loop
        """
        self._default_loop = WebLoop()
        return self._default_loop

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Set the current event loop
        """
        self._default_loop = loop

    def get_child_watcher(self):
        """
        Get the child watcher
        """
        raise NotImplementedError

    def set_child_watcher(self):
        """
        Set the child wather
        """
        raise NotImplementedError
