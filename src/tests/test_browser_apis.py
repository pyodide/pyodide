from pyodide_build.testing import run_in_pyodide

@run_in_pyodide
def test_hello_world():
    from js import eval
    f = eval("(x, y) => x+y")
    assert f(2,7) == 9


"""
Tests (TODO):
- set a timeout, cancel it and make sure it didn't run
- set a timeout, cancel it after and make sure it didn't crash
- set 2 or 3 timeouts, cancel one
"""