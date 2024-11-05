import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(firefox="slow")
@run_in_pyodide(packages=["altair"])
def test_altair(selenium):
    import altair as alt

    data = alt.Data(
        values=[
            {'a': 'A', 'b': 5},
            {'a': 'B', 'b': 3},
            {'a': 'C', 'b': 6},
            {'a': 'D', 'b': 7},
            {'a': 'E', 'b': 2}
        ]
    )
    c = alt.Chart(data).mark_bar().encode(x="a:N", y="b:Q").to_dict()

    assert c["mark"]["type"] == "bar"
    assert c["encoding"]["x"]["field"] == "a"
    assert c["encoding"]["y"]["type"] == "quantitative"
    assert "values" in c["data"]
