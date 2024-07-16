import pytest

from conftest import package_is_built


def test_duckdb(selenium):
    if not package_is_built("duckdb"):
        pytest.skip("duckdb not built")

    selenium.load_package(["duckdb"])
    selenium.run(
        """
        import duckdb

        with duckdb.connect() as con:
            (platform,) = con.execute("PRAGMA platform").fetchone()
            con.execute("CREATE TEMP TABLE t (id INT, content STRING)")
            con.execute("INSERT INTO t VALUES (42, 'hello'), (43, 'world')")
            query_result = con.execute("SELECT rowid, * FROM t ORDER BY rowid").fetchall()

        assert platform == "wasm_eh_pyodide"
        assert query_result == [(0, 42, "hello"), (1, 43, "world")]
        """
    )


def test_duckdb_with_pandas(selenium):
    packages = ["duckdb", "pandas"]

    for package in packages:
        if not package_is_built(package):
            pytest.skip(f"{package} not built")

    selenium.load_package(packages)
    selenium.run(
        """
        import duckdb
        import pandas as pd

        with duckdb.connect() as con:
            df = con.sql("SELECT UNNEST(RANGE(5)) as x ORDER BY x").df()

        expected = pd.DataFrame({"x": range(5)})
        assert df.equals(expected)
        """
    )
