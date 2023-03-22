import pathlib

import pytest
from pytest_pyodide import run_in_pyodide

TEST_DATA_PATH = pathlib.Path(__file__).parent / "test_data"


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["fiona"])
def test_supported_drivers(selenium):
    import fiona

    assert fiona.driver_count() > 0


@pytest.mark.driver_timeout(60)
def test_runtest(selenium):
    @run_in_pyodide(packages=["fiona", "pytest"])
    def _run(selenium, data):
        import zipfile

        with open("tests.zip", "wb") as f:
            f.write(data)

        with zipfile.ZipFile("tests.zip", "r") as zf:
            zf.extractall("tests")

        import sys

        sys.path.append("tests")

        import pytest

        def runtest(test_filter, ignore_filters):
            ignore_filter = []
            for ignore in ignore_filters:
                ignore_filter.append("--ignore-glob")
                ignore_filter.append(ignore)

            ret = pytest.main(
                [
                    "--pyargs",
                    "tests",
                    "--continue-on-collection-errors",
                    # "-v",
                    *ignore_filter,
                    "-k",
                    test_filter,
                ]
            )
            assert ret == 0

        runtest(
            (
                "not ordering "  # hangs
                "and not env "  # No module named "boto3"
                "and not slice "  # GML file format not supported
                "and not GML "  # GML file format not supported
                "and not TestNonCountingLayer "  # GPX file format not supported
                "and not test_schema_default_fields_wrong_type "  # GPX file format not supported
                "and not http "
                "and not FlatGeobuf"  # assertion error
            ),
            [
                "tests/test_fio*",  # no CLI tests
                "tests/test_data_paths.py",  # no CLI tests
                "tests/test_datetime.py",  # no CLI tests
                "tests/test_vfs.py",  # No module named "boto3"
            ],
        )

    TEST_DATA = (TEST_DATA_PATH / "fiona-tests-1.8.21.zip").read_bytes()
    _run(selenium, TEST_DATA)
