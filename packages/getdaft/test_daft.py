from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["getdaft"])
def test_catalog(selenium):
    import daft
    from daft import DataType

    import datetime

    df = daft.from_pydict({
        "integers": [1, 2, 3, 4],
        "floats": [1.5, 2.5, 3.5, 4.5],
        "bools": [True, True, False, False],
        "strings": ["a", "b", "c", "d"],
        "bytes": [b"a", b"b", b"c", b"d"],
        "dates": [datetime.date(1994, 1, 1), datetime.date(1994, 1, 2), datetime.date(1994, 1, 3), datetime.date(1994, 1, 4)],
        "lists": [[1, 1, 1], [2, 2, 2], [3, 3, 3], [4, 4, 4]],
        "nulls": [None, None, None, None],
    })
    df

    assert [1, 2, 3, 4] == df.select("integers").collect()
