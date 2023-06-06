import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["pyshp"])
def test_imports(selenium):
    import shapefile

    print(shapefile)

