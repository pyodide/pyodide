from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["jiter"])
def test_orjson(selenium):
    import jiter

    json_string = b'{"name": "Alice", "age": 30, "city": "New York"}'
    json_data = jiter.from_json(json_string)

    assert json_data == {"name": "Alice", "age": 30, "city": "New York"}
