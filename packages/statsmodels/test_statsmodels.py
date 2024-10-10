import pytest
from pytest_pyodide import run_in_pyodide


# Regression test for SciPy/OpenBLAS unresolved symbols
# i.e., pow_dd and pow_di
@pytest.mark.driver_timeout(160)
@run_in_pyodide(packages=["statsmodels", "pytest"])
def test_zero_collinear(selenium):
    import statsmodels as sm

    assert sm.test(["-svra", "-k", "test_zero_collinear"], exit=False)


# Regression test for scipy.optimize behaviour against illegal values
# for DLASCL parameter numbers
@pytest.mark.driver_timeout(160)
@run_in_pyodide(packages=["statsmodels", "pytest"])
def test_tuckey_hsd(selenium):
    import statsmodels as sm

    assert sm.test(["-svra", "-k", "TuckeyHSD"], exit=False)
