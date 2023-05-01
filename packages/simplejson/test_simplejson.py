# mypy: ignore-errors
from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["simplejson"])
def test_simplejson(selenium):
    from decimal import Decimal

    import simplejson

    # test whether C extensions have been built successfully
    import simplejson._speedups

    # test whether the basic functionality works
    dumped = simplejson.dumps({"c": 0, "b": 0, "a": 0}, sort_keys=True)
    expected = '{"a": 0, "b": 0, "c": 0}'
    assert dumped == expected

    # test Decimal functionality
    assert simplejson.loads("1.1", use_decimal=True) == Decimal("1.1")
