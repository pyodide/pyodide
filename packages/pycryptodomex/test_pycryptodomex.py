from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pycryptodomex"])
def test_pycryptodomex(selenium):
    from Cryptodome.Hash import MD5

    hasher = MD5.new()
    hasher.update(b"Hello, World!")
    assert hasher.hexdigest() == "65a8e27d8879283831b664bd8b7f0ad4"
