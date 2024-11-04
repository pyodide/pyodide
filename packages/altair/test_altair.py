import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(firefox="slow")
@run_in_pyodide(packages=["altair", "pandas"])
def test_altair(selenium):
    import altair as alt
    import pandas as pd

    data = pd.DataFrame(
        {
            "a": ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            "b": [28, 55, 43, 91, 81, 53, 19, 87, 52],
        }
    )
    c = alt.Chart(data).mark_bar().encode(x="a", y="b").to_dict()

    assert c["mark"]["type"] == "bar"
    assert c["encoding"]["x"]["field"] == "a"
    assert c["encoding"]["y"]["type"] == "quantitative"
    assert "name" in c["data"]
