from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["python-magic"])
def test_magic(selenium):
    from ctypes.util import find_library

    import magic

    buffer = b"abcde"
    assert magic.from_buffer(buffer) == "ASCII text, with no line terminators"
    assert magic.from_buffer(buffer, mime=True) == "text/plain"

    lib = find_library("magic")
    assert magic.from_file(lib) == "WebAssembly (wasm) binary module version 0x1 (MVP)"
    assert magic.from_file(lib, mime=True) == "application/octet-stream"
