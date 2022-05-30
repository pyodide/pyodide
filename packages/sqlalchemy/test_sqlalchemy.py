from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(packages=["sqlalchemy"])
def test_sqlalchemy(selenium):
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.connect() as conn:
        result = conn.execute(text("select 'hello world'"))
        assert result.all()[0] == ("hello world",)

        conn.execute(text("CREATE TABLE some_table (x int, y int)"))
        conn.execute(
            text("INSERT INTO some_table (x, y) VALUES (:x, :y)"),
            [{"x": 1, "y": 1}, {"x": 2, "y": 4}],
        )
        conn.commit()

        result = conn.execute(text("SELECT x, y FROM some_table")).all()
        assert len(result) == 2

        result = conn.execute(text("SELECT x, y FROM some_table WHERE x=2")).all()
        assert len(result) == 1
        assert result[0].y == 4
