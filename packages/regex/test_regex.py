from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["regex"])
def test_regex():
    import regex

    assert regex.search("o", "foo").end() == 2
