import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["python-flint"])
def test_python_flint(selenium):
    from flint import fmpz, fmpz_poly

    assert fmpz(1000) == 1000
    assert fmpz(1000).partitions_p() == 24061467864032622473692149727991
    a = fmpz_poly([1, 2, 3])
    b = fmpz_poly([2, 3, 4])
    assert a.gcd(a * b) == a


@pytest.mark.xfail_browsers(firefox="times out")
@run_in_pyodide(packages=["python-flint"])
def test_python_flint_tests(selenium):
    from flint.test.__main__ import main

    main("--tests", "--verbose")


@pytest.mark.parametrize(
    "module",
    [
        "flint.pyflint",
        "flint.flint_base.flint_base",
        "flint.flint_base.flint_context",
        "flint.types.fmpz",
        "flint.types.fmpz_poly",
        "flint.types.fmpz_mat",
        "flint.types.fmpz_series",
        "flint.types.fmpz_mod",
        "flint.types.fmpz_mod_poly",
        "flint.types.fmpq",
        "flint.types.fmpq_poly",
        "flint.types.fmpq_mat",
        "flint.types.fmpq_series",
        "flint.types.nmod",
        "flint.types.nmod_poly",
        "flint.types.nmod_mat",
        "flint.types.nmod_series",
        "flint.types.arf",
        "flint.types.arb",
        "flint.types.arb_poly",
        "flint.types.arb_mat",
        "flint.types.arb_series",
        "flint.types.acb",
        "flint.types.acb_poly",
        "flint.types.acb_mat",
        "flint.types.acb_series",
        "flint.types.dirichlet",
        "flint.functions.showgood",
    ],
)
@run_in_pyodide(packages=["python-flint"])
def test_python_flint_doctest(selenium, module):
    import doctest

    module = __import__(module)
    failure_count, test_count = doctest.testmod(module)
    assert failure_count == 0
