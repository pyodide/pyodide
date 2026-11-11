import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["test-sqlite3-extension"])
def test_sqlite3_load_extension(selenium):
    import sqlite3

    import sqlite3_extension_test

    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite3_extension_test.load(conn)
    conn.enable_load_extension(False)
    assert conn.execute("SELECT pyodide_answer()").fetchone() == (42,)
    conn.close()


@run_in_pyodide(packages=["pytest"])
def test_sqlite3_load_extension_disabled_by_default(selenium):
    import sqlite3

    import pytest

    conn = sqlite3.connect(":memory:")
    # Like in CPython, loading extensions must be enabled explicitly
    with pytest.raises(sqlite3.OperationalError, match="not authorized"):
        conn.execute("SELECT load_extension('/nonexistent')")
    conn.close()


@run_in_pyodide(packages=["pytest"])
def test_sqlite3_load_extension_missing_file(selenium):
    import sqlite3

    import pytest

    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    # A dlopen failure should raise a normal sqlite3 error
    with pytest.raises(sqlite3.OperationalError):
        conn.load_extension("/nonexistent")
    conn.close()
