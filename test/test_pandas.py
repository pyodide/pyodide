import pytest


@pytest.mark.skip
def test_pandas(selenium):
    selenium.load_package("pandas")
    assert len(selenium.run("import pandas\ndir(pandas)")) == 179


@pytest.mark.skip
def test_extra_import(selenium):
    selenium.load_package("pandas")
    selenium.run("from pandas import Series, DataFrame, Panel")
