from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["narwhals"])
def test_narwhals_from_native(selenium):
    import narwhals as nw

    class MyDictDataFrame:
        def __init__(self, data):
            self._data = data

        def __narwhals_dataframe__(self):
            return self

        @property
        def columns(self):
            return list(self._data)

    assert nw.from_native(
        MyDictDataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    ).columns == ["a", "b"]
