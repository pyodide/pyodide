import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(30)
@run_in_pyodide(packages=["vega_datasets"])
def test_vega_datasets(selenium):
    from vega_datasets import data

    assert len(data.list_datasets()) > 0

    df = data.iris()

    assert set(df.columns) == {
        "species",
        "petalLength",
        "sepalLength",
        "petalWidth",
        "sepalWidth",
    }
    assert data.iris.url is not None
    assert data.iris.filepath is not None
    assert data.iris.description is not None
