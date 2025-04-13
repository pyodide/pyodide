from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pycryptodome"])
def test_pycryptodome(selenium):
    from Crypto.Hash import MD5

    hasher = MD5.new()
    hasher.update(b"Hello, World!")
    assert hasher.hexdigest() == "65a8e27d8879283831b664bd8b7f0ad4"
