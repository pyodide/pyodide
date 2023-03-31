from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["idna"])
def test_idna(selenium_standalone):
    import idna

    assert idna.encode("ドメイン.テスト") == b"xn--eckwd4c7c.xn--zckzah"
