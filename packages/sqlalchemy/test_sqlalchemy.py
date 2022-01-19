from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["sqlalchemy"])
def test_sqlalchemy():
    import sqlalchemy

    engine = sqlalchemy.create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text("select 'hello world'"))
        assert result.all()[0] == ("hello world",)
