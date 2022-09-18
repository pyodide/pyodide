from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["regex"])
def test_regex(selenium):
    import regex

    assert regex.search("o", "foo").end() == 2
