from typing import Dict
import random

import pytest


def generate_largish_json(n_rows: int = 91746) -> Dict:
    # with n_rows = 91746, the output JSON size will be ~15 MB/10k rows

    # Note: we don't fix the random seed here, but the actual values
    # shouldn't matter
    columns = [
        ("column0", lambda: "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"),
        (
            "column1",
            lambda: random.choice(
                [
                    "notification-interval-longer",
                    "notification-interval-short",
                    "control",
                ]
            ),
        ),
        ("column2", lambda: random.choice([True, False])),
        ("column3", lambda: random.randint(0, 4)),
        ("column4", lambda: random.randint(0, 4)),
        ("column5", lambda: random.randint(0, 4)),
        ("column6", lambda: random.randint(0, 4)),
        ("column7", lambda: random.randint(0, 4)),
    ]
    data = {}
    for name, generator in columns:
        data[name] = [generator() for _ in range(n_rows)]
    return data


@pytest.mark.driver_timeout(30)
def test_pandas(selenium, request):
    selenium.load_package("pandas")
    assert len(selenium.run("import pandas\ndir(pandas)")) == 142


@pytest.mark.driver_timeout(30)
def test_extra_import(selenium, request):

    selenium.load_package("pandas")
    selenium.run("from pandas import Series, DataFrame, Panel")


@pytest.mark.driver_timeout(40)
@pytest.mark.skip_refcount_check
def test_load_largish_file(selenium_standalone, request, httpserver):
    selenium = selenium_standalone

    selenium.load_package("pandas")
    selenium.load_package("matplotlib")

    n_rows = 91746

    data = generate_largish_json(n_rows)

    httpserver.expect_request("/data").respond_with_json(
        data, headers={"Access-Control-Allow-Origin": "*"}
    )
    request_url = httpserver.url_for("/data")

    selenium.run(
        f"""
        import pyodide
        import matplotlib.pyplot as plt
        import pandas as pd

        df = pd.read_json(pyodide.open_url('{request_url}'))
        assert df.shape == ({n_rows}, 8)
        """
    )
