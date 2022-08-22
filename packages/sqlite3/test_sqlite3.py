from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "sqlite3"], pytest_assert_rewrites=False)
def test_sqlite3(selenium):
    from test import libregrtest

    name = "test_sqlite"
    ignore_tests = [
        "*MultiprocessTests*",
        "*ThreadTests*",
    ]

    try:
        libregrtest.main([name], ignore_tests=ignore_tests, verbose=True, verbose3=True)
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(f"Failed with code: {e.code}")


@run_in_pyodide(packages=["sqlite3"])
def test_sqlite3_basic(selenium):
    import sqlite3

    with sqlite3.connect(":memory:") as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE people (
                first_name VARCHAR,
                last_name VARCHAR
            )
        """
        )
        c.execute("INSERT INTO people VALUES ('John', 'Doe')")
        c.execute("INSERT INTO people VALUES ('Jane', 'Smith')")
        c.execute("INSERT INTO people VALUES ('Michael', 'Jordan')")
        c.execute("SELECT * FROM people")

    content = c.fetchall()
    assert len(content) == 3
    assert content[0][0] == "John"
    assert content[1][0] == "Jane"
    assert content[2][0] == "Michael"
