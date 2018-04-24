def test_pandas(selenium):
    selenium.run("import pandas")


def test_extra_import(selenium):
    selenium.run("from pandas import Series, DataFrame, Panel")
