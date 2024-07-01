from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "sqlite3"], pytest_assert_rewrites=False)
def test_sqlite3(selenium):
    import unittest

    import test.test_sqlite3

    suite = unittest.TestSuite(
        [unittest.TestLoader().loadTestsFromModule(test.test_sqlite3)]
    )

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    assert result.wasSuccessful()


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
