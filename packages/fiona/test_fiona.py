import base64
import pathlib

import pytest
from pytest_pyodide import run_in_pyodide

DEMO_PATH = pathlib.Path(__file__).parent / "test_data"
DATA_TEST = base64.b64encode((DEMO_PATH / "fiona-tests-1.8.21.zip").read_bytes())


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["fiona"])
def test_supported_drivers(selenium):
    import fiona

    assert fiona.driver_count() > 0
    # print(fiona.show_versions())


@pytest.mark.driver_timeout(60)
def test_runtest(selenium):
    selenium.load_package(["fiona", "pytest"])
    selenium.run(
        f"""
        import base64
        import zipfile
        with open("fiona-tests.zip", "wb") as f:
            f.write(base64.b64decode({DATA_TEST!r}))

        with zipfile.ZipFile("fiona-tests.zip", "r") as f:
            f.extractall("fiona-tests")

        import pytest
        import fiona
        import os
        os.environ["PROJ_LIB"] = fiona.env.PROJDataFinder().search()

        def runtest(filter):
            pytest.main(
                [
                    "--pyargs",
                    "fiona-tests",
                    "--continue-on-collection-errors",
                    "-vv",
                    "-k",
                    filter,
                ]
            )

        runtest("not ordering")
        """
    )
