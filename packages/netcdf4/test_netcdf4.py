from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["netcdf4"])
def test_netcdf4(selenium):
    import netCDF4

    rootgrp = netCDF4.Dataset("test.nc", "w", format="NETCDF4")
    assert rootgrp.data_model == "NETCDF4"
