from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pyarrow", "numpy", "pandas"])
def test_read_write_parquet(selenium):
    from arro3.core import Array, DataType

    arr = Array([1, 2, 3], DataType.int64())
