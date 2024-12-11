from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["apsw"])
async def apsw_test_helper(selenium):
    import apsw

    assert apsw.using_amalgamation

    connection = apsw.Connection(":memory:")
    connection.execute("create table point(x,y,z)")
    connection.execute("insert into point values(1, 2, 3)")
    row = connection.execute("select * from point").fetchone()
    assert row == (1, 2, 3)


def test_apsw(selenium):
    apsw_test_helper(selenium)
