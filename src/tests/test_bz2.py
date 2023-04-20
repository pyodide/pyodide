from pytest_pyodide import run_in_pyodide


@run_in_pyodide
def test_bz2(selenium):
    import bz2

    text = "Hello test test test test this is a test test test"
    some_compressed_bytes = bz2.compress(text.encode("utf-8"))
    assert some_compressed_bytes != text.encode("utf-8")
    decompressed_bytes = bz2.decompress(some_compressed_bytes)
    assert decompressed_bytes.decode("utf-8") == text
