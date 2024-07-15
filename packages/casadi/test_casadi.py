from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["casadi"])
def test_casadi(selenium):
    import casadi

    x = casadi.MX.sym("x")
    y = casadi.MX.sym("y")
    f = x**2 + y**2
    assert f(x=1, y=2) == 5
    assert f(x=3, y=4) == 25
    assert f(x=5, y=6) == 61
