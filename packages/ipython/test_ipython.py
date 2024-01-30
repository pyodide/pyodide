from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["ipython"])
def test_ipython(selenium):
    from IPython.lib import pretty

    assert pretty.pretty(1) == "1"
