from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["iminuit", "numpy", "pytest"])
def test_iminuit(selenium):
    import iminuit
    import iminuit.cost
    import numpy as np
    import pytest

    def line(x, α, β):
        return α + x * β

    np.random.seed(1)
    data_x = np.linspace(0, 1, 10)
    data_yerr = 0.1
    data_y = line(data_x, 1, 2) + data_yerr * np.random.randn(len(data_x))

    least_squares = iminuit.cost.LeastSquares(data_x, data_y, data_yerr, line)

    m = iminuit.Minuit(least_squares, α=0, β=0)  # starting values for α and β

    m.migrad()  # finds minimum of least_squares function
    m.hesse()  # accurately computes uncertainties

    assert m.values["α"] == pytest.approx(1, abs=0.5)
    assert m.values["β"] == pytest.approx(2, abs=0.5)
