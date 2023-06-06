import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["cartopy"])
def test_imports(selenium):
    pass


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["cartopy", "matplotlib"])
def test_matplotlib(selenium):
    import cartopy.crs as ccrs
    import matplotlib.pyplot as plt

    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.coastlines()

    plt.show()
