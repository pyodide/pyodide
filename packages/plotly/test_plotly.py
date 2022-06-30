from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(packages=["plotly"])
def test_plotly(selenium):
    import plotly.express as px

    df = px.data.gapminder().query("country=='Canada'")
    fig = px.line(df, x="year", y="lifeExp", title="Life expectancy in Canada")
    fig.show()
