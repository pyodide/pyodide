from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["cbor-diag"])
def test_cbor_diag(selenium_standalone):
    from cbor_diag import diag2cbor

    assert diag2cbor("{1: test'hello'}", to999=True) == bytes.fromhex(
        "a101d903e78264746573746568656c6c6f"
    )
