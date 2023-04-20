from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["multidict"])
def test_multidict(selenium_standalone):
    from multidict import MultiDict

    a = MultiDict({"1": 2})
    a.add("1", 3)
    assert a.getall("1") == [2, 3]
