from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["duckdb", "pandas"])
def test_duckdb(selenium):
    import duckdb
    import pandas as pd

    example_df = pd.DataFrame({"col_1": [1, 2, 3, 4, 5], "col_2": [10, 20, 30, 40, 50]})
    con = duckdb.connection(":memory:")
    query = """
    SELECT SUM(col_1) as sum_col_1, SUM(col_2) as sum_col_2
    FROM example_df
    """
    query_result = con.execute(query).fetchall()
    assert query_result[0][0] == 15
    assert query_result[1][0] == 150
