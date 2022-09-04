from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["duckdb"])
def test_duckdb(selenium):
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE t(id int, content string);")
    con.execute("INSERT INTO t VALUES (42, 'hello'), (43, 'world');")
    query_result = con.execute("SELECT rowid, id, content FROM t;").fetchall()
    con.close()
    assert query_result == [(0, 42, "hello"), (1, 43, "world")]
