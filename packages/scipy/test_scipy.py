from pyodide_test_runner import run_in_pyodide

run_in_pyodide_scipy = run_in_pyodide(
    module_scope=True,
    packages=["scipy"],
    # xfail_browsers={"chrome": "Times out in chrome"},
    driver_timeout=40,
)


@run_in_pyodide_scipy
def test_scipy_linalg():
    import numpy as np
    import scipy.linalg
    from numpy.testing import assert_allclose

    N = 10
    X = np.random.RandomState(42).rand(N, N)

    X_inv = scipy.linalg.inv(X)

    res = X.dot(X_inv)

    assert_allclose(res, np.identity(N), rtol=1e-07, atol=1e-9)


@run_in_pyodide_scipy
def test_brentq():
    from scipy.optimize import brentq

    brentq(lambda x: x, -1, 1)


@run_in_pyodide_scipy
def test_dlamch():
    from scipy.linalg import lapack

    lapack.dlamch("Epsilon-Machine")


@run_in_pyodide_scipy
def test_binom_ppf():
    from scipy.stats import binom

    assert binom.ppf(0.9, 1000, 0.1) == 112


@run_in_pyodide(module_scope=True, packages=["pytest", "scipy-tests"])
def test_scipy_pytest():
    import pytest

    def runtest(module, filter):
        pytest.main(
            [
                "--pyargs",
                f"scipy.{module}",
                "--continue-on-collection-errors",
                "-vv",
                "-k",
                filter,
            ]
        )

    runtest("odr", "explicit")
    runtest("signal.tests.test_ltisys", "TestImpulse2")
    runtest("stats.tests.test_multivariate", "haar")
