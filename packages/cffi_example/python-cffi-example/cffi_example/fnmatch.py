from ._fnmatch import lib
from .utils import to_bytes

FNM_PATHNAME = lib.FNM_PATHNAME
FNM_NOESCAPE = lib.FNM_NOESCAPE
FNM_PERIOD = lib.FNM_PERIOD


def fnmatch(pattern, name, flags=0):
    """Matches ``name`` against ``pattern``. Flags are a bitmask of:

    * ``FNM_PATHNAME``: No wildcard can match '/'.
    * ``FNM_NOESCAPE``: Backslashes don't quote special chars.
    * ``FNM_PERIOD``: Leading '.' is matched only explicitly.

    For example::

        >>> fnmatch("init.*", "init.d")
        True
        >>> fnmatch("foo", "bar")
        False
    """
    # fnmatch expects its arguments to be ``char[]``, so make sure that the
    # ``params`` and ``name`` are bytes/str (cffi will convert
    # bytes/str --> char[], but will refuse to convert unicode --> char[]).
    res = lib.fnmatch(to_bytes(pattern), to_bytes(name), flags)
    return res == 0
