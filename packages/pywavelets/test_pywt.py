from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["pywavelets"])
def test_pywt():
    import pywt
    import numpy as np

    def checkit(a, v):
        assert (np.rint(a) == v).all()

    x = [3, 7, 1, 1, -2, 5, 4, 6]
    cA, cD = pywt.dwt(x, "db2")
    w = pywt.Wavelet("sym3")
    checkit(pywt.idwt(cA, cD, "db2"), x)
    cA, cD = pywt.dwt(x, wavelet=w, mode="periodization")
    checkit(pywt.idwt(cA, cD, "sym3", "symmetric"), [1, 1, -2, 5])
    checkit(pywt.idwt(cA, cD, "sym3", "periodization"), x)
