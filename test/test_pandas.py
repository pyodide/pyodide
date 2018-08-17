import pytest


def test_pandas(selenium, request):
    if 'chrome' in selenium.__class__.__name__.lower():
        request.applymarker(pytest.mark.xfail(
            run=False, reason='chrome not supported'))
    selenium.load_package("pandas")
    assert len(selenium.run("import pandas\ndir(pandas)")) == 179


def test_extra_import(selenium, request):
    if 'chrome' in selenium.__class__.__name__.lower():
        request.applymarker(pytest.mark.xfail(
            run=False, reason='chrome not supported'))

    selenium.load_package("pandas")
    selenium.run("from pandas import Series, DataFrame, Panel")
