from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["brotli"])
def test_brotli(selenium):
    import brotli

    x64 = b"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    compress = brotli.compress(x64)
    assert compress == b"\x1b?\x00\xf8%\xf0\xe2\x8c\x00\xc0\x00"
    assert brotli.decompress(compress) == x64
