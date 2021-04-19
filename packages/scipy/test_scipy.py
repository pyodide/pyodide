from textwrap import dedent

import pytest


@pytest.mark.driver_timeout(40)
def test_scipy_linalg(selenium_standalone, request):
    selenium = selenium_standalone

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
def test_brentq(selenium_standalone):
    selenium_standalone.load_package("scipy")
    selenium_standalone.run("from scipy.optimize import brentq")
    selenium_standalone.run("brentq(lambda x: x, -1, 1)")
