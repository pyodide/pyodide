from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["ipython"])
def test_ipython_lib_pretty(selenium):
    from IPython.lib import pretty

    assert pretty.pretty(1) == "1"
    assert (
        pretty.pretty({i: "*" * i for i in range(8)})
        == "{0: '',\n 1: '*',\n 2: '**',\n 3: '***',\n 4: '****',\n 5: '*****',\n 6: '******',\n 7: '*******'}"
    )
