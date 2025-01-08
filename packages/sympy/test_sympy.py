from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["sympy"])
def test_sympy(selenium):
    import sympy

    a, b = sympy.symbols("a,b")
    c = sympy.sqrt(a**2 + b**2)

    assert c.subs({a: 3, b: 4}) == 5

    # Uses python-flint if installed
    x = sympy.symbols("x")
    assert (x**2 - 1).factor() == (x + 1) * (x - 1)
