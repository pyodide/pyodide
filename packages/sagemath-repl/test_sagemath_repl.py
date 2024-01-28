import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["sagemath-repl"])
def test_sagemath_repl(selenium):
    import sage.all__sagemath_repl
