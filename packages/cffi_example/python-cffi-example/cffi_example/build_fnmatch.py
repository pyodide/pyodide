import os

from cffi import FFI

ffi = FFI()

ffi.set_source(
    "cffi_example._fnmatch",
    # Since we are calling fnmatch directly no custom source is necessary. We
    # need to #include <fnmatch.h>, though, because behind the scenes cffi
    # generates a .c file which contains a Python-friendly wrapper around
    # ``fnmatch``:
    #    static PyObject *
    #    _cffi_f_fnmatch(PyObject *self, PyObject *args) {
    #        ... setup ...
    #        result = fnmatch(...);
    #        return PyInt_FromLong(result);
    #    }
    "#include <fnmatch.h>",
    # The important thing is to inclue libc in the list of libraries we're
    # linking against:
    libraries=["c"],
)

with open(os.path.join(os.path.dirname(__file__), "fnmatch.h")) as f:
    ffi.cdef(f.read())

if __name__ == "__main__":
    ffi.compile()
