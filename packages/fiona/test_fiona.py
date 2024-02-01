import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["fiona"])
def test_supported_drivers(selenium):
    import fiona

    assert fiona.driver_count() > 0


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["fiona-tests", "pytest"])
def test_fiona(selenium_standalone):
    import site
    import sys

    import pytest

    sys.path.append(site.getsitepackages()[0] + "/fiona-tests")

    def runtest(test_filter):
        ret = pytest.main(
            [
                "--pyargs",
                "tests",
                "--continue-on-collection-errors",
                # "-v",
                "-k",
                test_filter,
            ]
        )
        assert ret == 0

    runtest(
        " not ordering "  # hangs
        " and not env "  # No module named "boto3"
        " and not slice "  # GML file format not supported
        " and not GML "  # GML file format not supported
        " and not TestNonCountingLayer "  # GPX file format not supported
        " and not test_schema_default_fields_wrong_type "  # GPX file format not supported
        " and not http "
        " and not FlatGeobuf"  # assertion error
        " and not esri_only_wkt"  # format not supported
    )
