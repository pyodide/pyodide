from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["duckdb"])
def test_duckdb(selenium):
    import duckdb

    con = duckdb.connect()
    (platform,) = con.execute("PRAGMA platform").fetchone()
    assert platform == "wasm_eh_pyodide"

    (a, b) = con.execute("SELECT 1 AS a, 'a' AS b").fetchone()
    assert a == 1
    assert b == "a"
