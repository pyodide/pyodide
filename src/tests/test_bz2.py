from pyodide_test_runner import run_in_pyodide


@run_in_pyodide
def test_bz2():
    import bz2

    text = "Hello test test test test this is a test test test"
    some_compressed_bytes = bz2.compress(text.encode("utf-8"))
    assert some_compressed_bytes != text
    decompressed_bytes = bz2.decompress(some_compressed_bytes)
    assert decompressed_bytes.decode("utf-8") == text
