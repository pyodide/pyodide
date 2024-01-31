import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["sagemath-categories"])
def test_sagemath_categories(selenium):
    import sage.all__sagemath_categories


@pytest.mark.driver_timeout(3600)
@run_in_pyodide(packages=["sagemath-categories", "sagemath-repl"])
def test_sagemath_categories_doctests(selenium):
    from sage.doctest.control import DocTestController, DocTestDefaults

    args = DocTestDefaults()
    args.installed = True
    args.environment = "sage.all__sagemath_categories"
    args.global_iterations = 1
    DC = DocTestController(args, [])
    err = DC.run()
    assert err == 0
