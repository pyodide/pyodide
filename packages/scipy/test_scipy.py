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


@pytest.mark.skip_pyproxy_check
@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["pytest", "scipy-tests", "micropip"])
async def test_scipy_pytest(selenium):
    import pytest

    import micropip

    await micropip.install("hypothesis")

    def runtest(module, filter):
        result = pytest.main(
            [
                "--pyargs",
                f"scipy.{module}",
                "--continue-on-collection-errors",
                "-vv",
                "-k",
                filter,
            ]
        )
        assert result == 0

    runtest("odr", "explicit")
    runtest("signal.tests.test_ltisys", "TestImpulse2")
    runtest("stats.tests.test_multivariate", "haar")
    runtest("sparse.linalg._eigen", "test_svds_parameter_k_which")


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


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy"])
def test_dblquad(selenium):
    import scipy.integrate

    unit_square_area = scipy.integrate.dblquad(
        lambda y, x: 1, 0, 1, lambda x: 0, lambda x: 1
    )
    assert (
        abs(unit_square_area[0] - 1) < unit_square_area[1]
    ), f"Unit square area calculated using scipy.integrate.dblquad of {unit_square_area[0]} (+- {unit_square_area[0]}) is too far from 1.0"


import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any


def check_emscripten():
    if not shutil.which("emcc"):
        pytest.skip("Needs Emscripten")


@contextmanager
def venv_ctxmgr(path):
    check_emscripten()

    if TYPE_CHECKING:
        create_pyodide_venv: Any = None
    else:
        from pyodide_build.out_of_tree.venv import create_pyodide_venv

    create_pyodide_venv(path)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="module")
def venv(runtime):
    if runtime != "node":
        pytest.xfail("node only")
    check_emscripten()
    path = Path(".venv-pyodide-tmp-test")
    with venv_ctxmgr(path) as venv:
        yield venv


def install_pkg(venv, pkgname):
    return subprocess.run(
        [
            venv / "bin/pip",
            "install",
            pkgname,
            "--disable-pip-version-check",
        ],
        capture_output=True,
        encoding="utf8",
    )


def test_cmdline_runner(selenium, venv):
    result = install_pkg(venv, "scipy")
    assert result.returncode == 0
    result = subprocess.run(
        [venv / "bin/python", Path(__file__).parent / "cmdline_test_file.py"]
    )
    print(result.stdout)
    print(result.stderr)
    assert result.returncode == 0
