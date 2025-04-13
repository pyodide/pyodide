from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["cbor-diag"])
def test_cbor_diag(selenium_standalone):
    from cbor_diag import diag2cbor

    assert diag2cbor('{1: "hello"}') == bytes.fromhex("a1016568656c6c6f")
