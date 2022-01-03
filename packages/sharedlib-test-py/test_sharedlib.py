from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["sharedlib-test-py"])
def test_sharedlib():
    from sharedlib_test import do_the_thing

    assert do_the_thing(4, 5) == 29
