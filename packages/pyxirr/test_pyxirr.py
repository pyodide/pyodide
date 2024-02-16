from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pyxirr"])
def test_pyxirr(selenium):
    import pyxirr

    cf = [
        ("2020-01-01", -10000),
        ("2021-01-01", 5500),
        ("2022-01-01", 6000),
    ]
    rate = pyxirr.xirr(cf)
    assert rate == 0.09677887172566714
