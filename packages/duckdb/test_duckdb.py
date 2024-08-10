import pytest
from pytest_pyodide import run_in_pyodide

from conftest import package_is_built


def skip_if_not_installed(packages):
    for package in packages:
        if not package_is_built(package):
            pytest.skip(f"{package} not built")


def test_duckdb(selenium):
    packages = ["duckdb"]

    skip_if_not_installed(packages)

    selenium.load_package(packages)

    @run_in_pyodide
    def do_test(selenium):
        import duckdb

        with duckdb.connect() as con:
            (platform,) = con.execute("PRAGMA platform").fetchone()
            con.execute("CREATE TEMP TABLE t (id INT, content STRING)")
            con.execute("INSERT INTO t VALUES (42, 'hello'), (43, 'world')")
            query_result = con.execute(
                "SELECT rowid, * FROM t ORDER BY rowid"
            ).fetchall()

        assert "pyodide" in platform
        assert "wasm" in platform
        assert query_result == [(0, 42, "hello"), (1, 43, "world")]

    do_test(selenium)


@pytest.mark.driver_timeout(60)
def test_duckdb_with_pandas(selenium):
    packages = ["duckdb", "pandas"]

    skip_if_not_installed(packages)

    selenium.load_package(packages)

    @run_in_pyodide
    def do_test(selenium):
        import duckdb
        import pandas as pd

        with duckdb.connect() as con:
            df = con.sql("SELECT UNNEST(RANGE(5)) as x ORDER BY x").df()

        expected = pd.DataFrame({"x": range(5)})
        assert df.equals(expected)

    do_test(selenium)
