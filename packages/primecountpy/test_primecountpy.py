from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["primecountpy"])
def test_pplpy(selenium):
    import primecountpy as primecount

    assert primecount.prime_pi(1000) == 168
