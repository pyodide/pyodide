from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["xarray"])
def test_xarray(selenium):
    import xarray as xr

    da = xr.DataArray(data=[[0, 1, 2], [3, 4, 5]], dims=("x", "y"))
    xr.testing.assert_equal(a=da.mean(), b=xr.DataArray(data=2.5))
