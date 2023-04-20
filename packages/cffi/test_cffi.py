from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["cffi"])
def test_cffi_asprintf(selenium):
    from cffi import FFI

    ffi = FFI()
    ffi.cdef(
        """int asprintf(char** buf, const char *format, ...);   // copy-pasted from the man page"""
    )
    C = ffi.dlopen(None)  # loads the entire C namespace
    buf = ffi.new("char**")
    arg1 = ffi.new("char[]", b"wo")
    arg2 = ffi.new("char[]", b"ld")
    C.asprintf(buf, b"hello %sr%s", arg1, arg2)
    assert ffi.string(buf[0]).decode() == "hello world"
