from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["yarl"])
def test_yarl(selenium_standalone):
    from yarl import URL

    url = URL("https://www.python.org/~guido?arg=1#frag")
    assert url.host == "www.python.org"
    assert url.query_string == "arg=1"
