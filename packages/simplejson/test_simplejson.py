from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["simplejson"])
def test_simplejson(selenium):
    import simplejson

    # test whether the basic functionality works
    dumped = simplejson.dumps({"c": 0, "b": 0, "a": 0}, sort_keys=True)
    expected = '{"a": 0, "b": 0, "c": 0}'
    assert dumped == expected

    # test whether C extensions have been built succesfully
    import simplejson._speedups
