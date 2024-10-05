from pytest_pyodide import run_in_pyodide

from conftest import package_is_built

import pytest


def skip_if_not_installed(packages):
    for package in packages:
        if not package_is_built(package):
            pytest.skip(f"{package} not built")


@run_in_pyodide(packages=["sympy"])
def test_sympy(selenium):
    import sympy

    a, b = sympy.symbols("a,b")
    c = sympy.sqrt(a**2 + b**2)

    assert c.subs({a: 3, b: 4}) == 5


def test_sympy_and_python_flint(selenium):
    skip_if_not_installed(["sympy", "python-flint"])

    @run_in_pyodide(packages=["sympy", "python-flint"])
    def run(selenium):
        import sympy
        from sympy.external.gmpy import GROUND_TYPES

        assert GROUND_TYPES == "flint"

        # Use python-flint for factorisation:
        x = sympy.symbols("x")
        assert (x**2 - 1).factor() == (x + 1) * (x - 1)

    run()
