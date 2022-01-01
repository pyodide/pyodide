from textwrap import dedent

import pytest
from conftest import selenium_context_manager


@pytest.mark.driver_timeout(40)
def test_scipy_linalg(selenium_module_scope, request):
    with selenium_context_manager(selenium_module_scope) as selenium:

        selenium.load_package("scipy")
        cmd = dedent(
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

        selenium.run(cmd)


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
        from scipy.linalg import lapack
        lapack.dlamch('Epsilon-Machine')

@pytest.mark.driver_timeout(40)
def test_logistic_regression(selenium_module_scope):
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("scipy")
        selenium.run(
            """
            from sklearn.datasets import load_iris
            from sklearn.linear_model import LogisticRegression
            X, y = load_iris(return_X_y=True)
            clf = LogisticRegression(random_state=0).fit(X, y)
            print(clf.predict(X[:2, :]))
            print(clf.predict_proba(X[:2, :]))
            print(clf.score(X, y))
            """
        )
