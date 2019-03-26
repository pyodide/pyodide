def test_sqlite3(selenium):
    content = selenium.run("""
        import sqlite3

        with sqlite3.connect(':memory:') as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE people (
                    first_name VARCHAR,
                    last_name VARCHAR
                )
            ''')
            c.execute("INSERT INTO people VALUES ('John', 'Doe')")
            c.execute("INSERT INTO people VALUES ('Jane', 'Smith')")
            c.execute("INSERT INTO people VALUES ('Michael', 'Jordan')")
            c.execute("SELECT * FROM people")
    """)
    content = selenium.run("c.fetchall()")
    assert len(content) == 3
    assert content[0][0] == 'John'
    assert content[1][0] == 'Jane'
    assert content[2][0] == 'Michael'
