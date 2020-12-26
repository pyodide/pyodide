import heapq
import asyncio
import time
import traceback

class WebLoop(asyncio.AbstractEventLoop):
    """A simple custom loop for asyncio
    Adapted from the EventSimulator made by @damonjw
    https://gist.github.com/damonjw/35aac361ca5d313ee9bf79e00261f4ea
    """

    def __init__(self, debug=False, interval=10):
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
        self._exception_handler = self._default_exception_handler

    def get_debug(self):
        return self._debug

    def time(self):
        return time.time()

    def run_forever(self):
        self._stop = False
        if asyncio.get_event_loop() == self:
            asyncio._set_running_loop(self)
        if not self._running:
            self._do_tasks(forever=True)

    def run_until_complete(self, future):
        asyncio.ensure_future(future)
        if asyncio.get_event_loop() == self:
            asyncio._set_running_loop(self)
        self._stop = False
        if not self._running:
            self._do_tasks(until_complete=True)

    def _do_tasks(self, until_complete=False, forever=False):
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

        if forever or (
            until_complete
            and (
                self._immediate or self._scheduled or self._next_handle or self._futures
            )
        ):
            self._timeout_promise(self._interval).then(
                lambda x: self._do_tasks(until_complete=until_complete, forever=forever)
            )
        else:
            self._quit_running()

    def _quit_running(self):
        if asyncio.get_event_loop() == self:
            asyncio._set_running_loop(None)
        self._running = False

    def _default_exception_handler(self, loop, context):
        js.console.error(context.get("message"))

    def default_exception_handler(self):
        return self._default_exception_handler

    def _timer_handle_cancelled(self, handle):
        pass

    def is_running(self):
        return self._running

    def is_closed(self):
        return not self._running

    def stop(self):
        self._stop = True
        self._quit_running()

    def close(self):
        self._stop = True
        self._quit_running()

    def shutdown_asyncgens(self):
        raise NotImplementedError

    def shutdown_default_executor(self):
        raise NotImplementedError

    def call_exception_handler(self, context):
        self._exception_handler(self, context)

    def set_exception_handler(self, handler):
        self._exception_handler = handler

    def get_exception_handler(self):
        return self._exception_handler

    def call_soon(self, callback, *args, **kwargs):
        h = asyncio.Handle(callback, args, self)
        self._immediate.append(h)
        return h

    def call_later(self, delay, callback, *args):
        if delay < 0:
            raise Exception("Can't schedule in the past")
        return self.call_at(self.time() + delay, callback, *args)

    def call_at(self, when, callback, *args):
        if when < self.time():
            raise Exception("Can't schedule in the past")
        h = asyncio.TimerHandle(when, callback, args, self)
        heapq.heappush(self._scheduled, h)
        h._scheduled = True
        return h

    def create_task(self, coro):
        async def wrapper():
            try:
                await coro
            except Exception as e:
                self.call_exception_handler(
                    {"message": traceback.format_exc(), "exception": e}
                )

        return asyncio.Task(wrapper(), loop=self)

    def create_future(self):
        fut = asyncio.Future(loop=self)

        def remove_fut(*args):
            self._futures.remove(fut)

        fut.add_done_callback(remove_fut)
        self._futures.append(fut)
        return fut

class WebLoopPolicy(asyncio.DefaultEventLoopPolicy):
    def __init__(self):
        self._default_loop = None

    def get_event_loop(self):
        if self._default_loop is None:
            self._default_loop = WebLoop()
        return self._default_loop

    def new_event_loop(self):
        self._default_loop = WebLoop()
        return self._default_loop

    def set_event_loop(self, loop):
        self._default_loop = loop

    def get_child_watcher(self):
        raise NotImplementedError

    def set_child_watcher(self):
        raise NotImplementedError
