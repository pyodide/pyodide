import pytest
from pyodide_test_runner import run_in_pyodide


@pytest.mark.xfail_browsers(chrome="xfail")
@run_in_pyodide(packages=["pywavelets"], driver_timeout=30)
def test_pywt(selenium):
    import numpy as np
    import pywt

    def checkit(a, v):
        assert (np.rint(a) == v).all()

    x = [3, 7, 1, 1, -2, 5, 4, 6]
    cA, cD = pywt.dwt(x, "db2")
    w = pywt.Wavelet("sym3")
    checkit(pywt.idwt(cA, cD, "db2"), x)
    cA, cD = pywt.dwt(x, wavelet=w, mode="periodization")
    checkit(pywt.idwt(cA, cD, "sym3", "symmetric"), [1, 1, -2, 5])
    checkit(pywt.idwt(cA, cD, "sym3", "periodization"), x)
