from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["mmh3"])
def test_mmh3(selenium):
    import mmh3

    assert (-2129773440516405919, 9128664383759220103) == mmh3.hash64("foo")
    assert b"aE\xf5\x01W\x86q\xe2\x87}\xba+\xe4\x87\xaf~" == mmh3.hash_bytes("foo")
