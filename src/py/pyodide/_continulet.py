from _pyodide_core import _switch


class Continulet:
    def __eq__(self, other):
        return self is other

    def __init__(self, func, *args, **kwargs):
        if hasattr(self, "_func"):
            raise RuntimeError("continulet already __init__ialized")
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._continuation = None
        self._finished = False

    def is_pending(self):
        return hasattr(self, "_func") and not self._finished

    def switch(self, value=None, to=None):
        return _switch(self, None, 0, value, to)

    def throw(self, err, to=None):
        return _switch(self, None, 1, err, to)

def permute(*contlist):
    for cont in contlist:
        if cont._finished:
            raise RuntimeError("got an already-finished continulet")
    # ignore non-initialized continulets
    contlist = [ cont for cont in contlist if hasattr(cont, "_func")]
    if len(contlist) <= 1:
        return
    otherc = contlist[-1]._continuation
    for cont in contlist:
        otherc, cont._continuation = cont._continuation, otherc

