from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pyproj"])
def test_pyproj(selenium):
    from pyproj import CRS, Transformer

    latlon = CRS.from_epsg(4326)

    # Check major axis radius of Earth for this projection
    assert latlon.get_geod().a == 6378137

    lcc = CRS.from_proj4("+proj=lcc +lat_1=25 +lat_2=40 +lat_0=35 +lon_0=-90")
    t = Transformer.from_crs(latlon, lcc)

    # Check that this transform gets us the origin
    x, y = t.transform(35, -90)
    assert int(x) == 0
    assert int(y) == 0
