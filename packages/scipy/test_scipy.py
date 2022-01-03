import pytest
from conftest import selenium_context_manager


@pytest.mark.driver_timeout(40)
def test_scipy_linalg(selenium_module_scope):
    if selenium_module_scope.browser == "chrome":
        pytest.xfail("Times out in chrome")
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("scipy")
        selenium.run(
            r"""
            import numpy as np
            import scipy as sp
            import scipy.linalg
            from numpy.testing import assert_allclose

            N = 10
            X = np.random.RandomState(42).rand(N, N)

            X_inv = scipy.linalg.inv(X)

            res = X.dot(X_inv)

            assert_allclose(res, np.identity(N),
                            rtol=1e-07, atol=1e-9)
            """
        )


@pytest.mark.driver_timeout(40)
def test_brentq(selenium_module_scope):
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("scipy")
        selenium.run(
            """
            from scipy.optimize import brentq
            brentq(lambda x: x, -1, 1)
            """
        )


@pytest.mark.driver_timeout(40)
def test_dlamch(selenium_module_scope):
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("scipy")
        selenium.run(
            """
            from scipy.linalg import lapack
            lapack.dlamch('Epsilon-Machine')
            """
        )
