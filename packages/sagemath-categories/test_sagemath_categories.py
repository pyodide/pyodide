from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["sagemath-categories"])
def test_sagemath_categories(selenium):
    pass


@run_in_pyodide(packages=["sagemath-categories", "sagemath-repl"])
def test_sagemath_categories_doctests(selenium):
    from sage.doctest.control import DocTestController, DocTestDefaults

    args = DocTestDefaults()
    args.stats_path = None
    args.installed = True
    DC = DocTestController(args, [])
    err = DC.run()
    assert err == 0
