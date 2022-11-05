from pyodide.ffi import create_proxy
from pyodide_js._module import (  # type:ignore[import]
    continuletPromiseRace,
    continuletRun,
)


class Continulet:
    def __init__(self, func, *args, **kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._continuation = None
        self._csp = None

    def _start(self):
        def func():
            try:
                return self._func(self, *self._args, **self._kwargs)
            except BaseException as e:
                return e

        self._csp = continuletRun(func)[0]

    def switch(self, value=None):
        from js import Promise

        resolve = None

        def store_res(r, _):
            nonlocal resolve
            resolve = r

        p = Promise.new(store_res)
        cont = self._continuation
        self._continuation = resolve

        if cont:
            cont(create_proxy([0, value]))
        else:
            if value is not None:
                raise TypeError(
                    "can't send non-None value to a just-started continulet"
                )

            def func():
                try:
                    return [0, self._func(self, *self._args, **self._kwargs)]
                except BaseException as e:
                    return [1, e]

            self._csp = continuletRun(func)[0]

        r = continuletPromiseRace(self._csp, p)[0].syncify()
        if hasattr(r, "unwrap"):
            s = r
            r = r.unwrap()
            s.destroy()
        [status, result] = r
        if status == 0:
            return result
        else:
            raise result
