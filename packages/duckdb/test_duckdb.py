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
