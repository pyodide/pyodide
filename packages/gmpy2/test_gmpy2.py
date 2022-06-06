from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(packages=["gmpy2"])
def test_gmpy2(selenium):
    import gmpy2
    from gmpy2 import mpc, mpfr, mpq, mpz, sqrt

    assert mpz(99) * 43 == mpz(4257)
    assert mpq(3, 7) / 7 == mpq(3, 49)

    gmpy2.get_context().allow_complex = True
    assert sqrt(mpfr(-2)) == mpc("0.0+1.4142135623730951j")
