import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy"])
def test_scipy_linalg(selenium):
    import numpy as np
    import scipy.linalg
    from numpy.testing import assert_allclose

    N = 10
    X = np.random.RandomState(42).rand(N, N)

    X_inv = scipy.linalg.inv(X)

    res = X.dot(X_inv)

    assert_allclose(res, np.identity(N), rtol=1e-07, atol=1e-9)


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy"])
def test_brentq(selenium):
    from scipy.optimize import brentq

    brentq(lambda x: x, -1, 1)


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy"])
def test_dlamch(selenium):
    from scipy.linalg import lapack

    lapack.dlamch("Epsilon-Machine")


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy"])
def test_binom_ppf(selenium):
    from scipy.stats import binom

    assert binom.ppf(0.9, 1000, 0.1) == 112


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy"])
def test_simple(selenium):
    import numpy as np
    from scipy.special import powm1

    powm1(np.nan, 1)


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["pytest", "scipy-tests"])
def test_scipy_pytest(selenium):
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
    runtest("sparse.linalg._eigen", "test_svds_parameter_k_which")
    # runtest("fft.tests.test_multithreading", "test_threaded_same and 2-fft2")
    # runtest("optimize.tests.test_zeros", "gh3089_8394")
    # runtest("sparse.linalg._dsolve.tests", "spilu_nnz0")
    # runtest("special.tests.test_cython_special", "test_cython_api and erfinv")
    # runtest("stats.tests.test_continuous_basic", "studentized_range-args96-isf")


@pytest.mark.driver_timeout(10)
@pytest.mark.parametrize(
    "module,filter",
    [
        ("odr", "explicit"),
        ("signal.tests.test_ltisys", "TestImpulse2"),
        ("stats.tests.test_multivariate", "haar"),
        ("sparse.linalg._eigen", "test_svds_parameter_k_which"),
        ("fft.tests.test_multithreading", "test_threaded_same and 2-fft2"),
        ("optimize.tests.test_zeros", "gh3089_8394"),
        ("sparse.linalg._dsolve.tests", "spilu_nnz0"),
        ("special.tests.test_cython_special", "test_cython_api and erfinv"),
        ("stats.tests.test_continuous_basic", "studentized_range-args96-isf"),
    ],
)
@run_in_pyodide(packages=["pytest", "scipy-tests"])
def test_scipy_pytest_parametrized(selenium, module, filter):
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

    runtest(module, filter)


@pytest.mark.driver_timeout(10)
@run_in_pyodide(packages=["scipy-tests"])
def test_mine(selenium):
    from scipy.sparse import csc_matrix
    from scipy.sparse.linalg._dsolve import spilu

    A = csc_matrix((5, 5), dtype="d")
    spilu(A)


# @pytest.mark.driver_timeout(40)
# @run_in_pyodide(packages=["pytest", "scipy-tests"])
# def test_scipy_pytest_fft(selenium):
#     import pytest

#     runtest("fft.tests.test_multithreading", "test_threaded_same and 2-fft2")


# @pytest.mark.driver_timeout(40)
# @run_in_pyodide(packages=["pytest", "scipy-tests"])
# def test_scipy_pytest_optimize(selenium):
#     import pytest

#     runtest("optimize.tests.test_zeros", "gh3089_8394")

# @pytest.mark.driver_timeout(40)
# @run_in_pyodide(packages=["pytest", "scipy-tests"])
# def test_scipy_pytest_linalg(selenium):
#     import pytest

#     runtest("sparse.linalg._dsolve.tests", "spilu_nnz0")

# @pytest.mark.driver_timeout(40)
# @run_in_pyodide(packages=["pytest", "scipy-tests"])
# def test_scipy_pytest_special(selenium):
#     import pytest

#     runtest("special.tests.test_cython_special", "test_cython_api and erfinv")

# @pytest.mark.driver_timeout(40)
# @run_in_pyodide(packages=["pytest", "scipy-tests"])
# def test_scipy_pytest_stats(selenium):
#     import pytest

#     runtest("stats.tests.test_continuous_basic", "studentized_range-args96-isf")


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy"])
def test_cpp_exceptions(selenium):
    import numpy as np
    import pytest
    from scipy.spatial.distance import cdist

    out = np.ones((2, 2))
    arr = np.array([[1, 2]])

    with pytest.raises(ValueError, match="Output array has incorrect shape"):
        cdist(arr, arr, out=out)
    from scipy.sparse._sparsetools import test_throw_error

    with pytest.raises(MemoryError):
        test_throw_error()
    from scipy.signal import lombscargle

    with pytest.raises(ValueError):
        lombscargle(x=[1], y=[1, 2], freqs=[1, 2, 3])


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy"])
def test_logm(selenium_standalone):
    import numpy as np
    from numpy import eye, random
    from scipy.linalg import logm

    random.seed(1234)
    dtype = np.float64
    n = 2
    scale = 1e-4
    A = (eye(n) + random.rand(n, n) * scale).astype(dtype)
    logm(A)
