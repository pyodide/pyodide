from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["orjson"])
def test_orjson(selenium):
    import orjson

    json_string = '{"name": "Alice", "age": 30, "city": "New York"}'
    json_data = orjson.loads(json_string)

    assert json_data == {"name": "Alice", "age": 30, "city": "New York"}
