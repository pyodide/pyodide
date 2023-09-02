from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["srsly"])
def test_srsly(selenium):
    import srsly

    data = {"foo": "bar", "baz": 123}
    json_string = srsly.json_dumps(data)
    assert json_string == '{"foo":"bar","baz":123}'
