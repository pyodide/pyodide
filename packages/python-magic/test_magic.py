from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["python-magic"])
def test_magic(selenium):
    import site

    import magic

    buffer = b"abcde"
    assert magic.from_buffer(buffer) == "ASCII text, with no line terminators"
    assert magic.from_buffer(buffer, mime=True) == "text/plain"

    site_packages = site.getsitepackages()[0]
    filename = site_packages + "/libmagic.so"
    assert (
        magic.from_file(filename)
        == "WebAssembly (wasm) binary module version 0x1 (MVP)"
    )
    assert magic.from_file(filename, mime=True) == "application/octet-stream"
