from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(packages=["gmpy2"])
def test_sympy(selenium):
    from gmpy2 import mpz

    assert mpz(99) * 43 == mpz(4257)
