from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["sympy"])
def test_sympy():
    import sympy

    a, b = sympy.symbols("a,b")
    c = sympy.sqrt(a**2 + b**2)

    assert c.subs({a: 3, b: 4}) == 5
