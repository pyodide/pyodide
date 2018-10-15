import pytest


def test_pandas(selenium, request):
    if selenium.browser == 'chrome':
        request.applymarker(pytest.mark.xfail(
            run=False, reason='chrome not supported'))
    selenium.load_package("pandas")
    assert len(selenium.run("import pandas\ndir(pandas)")) == 140


def test_extra_import(selenium, request):
    if selenium.browser == 'chrome':
        request.applymarker(pytest.mark.xfail(
            run=False, reason='chrome not supported'))

    selenium.load_package("pandas")
    selenium.run("from pandas import Series, DataFrame, Panel")


def test_load_largish_file(selenium_standalone, request):
    selenium = selenium_standalone

    if selenium.browser == 'chrome':
        request.applymarker(pytest.mark.xfail(
            run=False, reason='chrome not supported'))

    selenium.load_package("pandas")
    selenium.load_package("matplotlib")

    selenium.run("""
        import pyodide
        import matplotlib.pyplot as plt
        import pandas as pd

        pd.read_json(pyodide.open_url('test/largish.json.cgi'))
    """)
