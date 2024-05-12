from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["duckdb"])
def test_duckdb(selenium):
    import duckdb

    with duckdb.connect() as con:
        (platform,) = con.execute("PRAGMA platform").fetchone()
        con.execute("CREATE TEMP TABLE t (id INT, content STRING)")
        con.execute("INSERT INTO t VALUES (42, 'hello'), (43, 'world')")
        query_result = con.execute("SELECT rowid, * FROM t").fetchall()

    assert platform == "wasm_eh_pyodide"
    assert query_result == [(0, 42, "hello"), (1, 43, "world")]


@run_in_pyodide(packages=["duckdb", "pandas"])
def test_duckdb_with_pandas(selenium):
    import duckdb
    import pandas as pd

    with duckdb.connect() as con:
        df = con.sql("SELECT UNNEST(RANGE(5)) as x").df()

    expected = pd.DataFrame({"x": range(5)})
    assert df.equals(expected)
