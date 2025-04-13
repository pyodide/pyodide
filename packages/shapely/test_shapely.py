from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["shapely"])
def test_shapely(selenium):
    from shapely.geometry import MultiLineString

    coords = [((0, 0), (1, 1)), ((-1, 0), (1, 0))]
    lines = MultiLineString(coords)
    assert lines.area == 0.0
    assert round(lines.length, 2) == 3.41


@run_in_pyodide(packages=["shapely"])
def test_shapely_geos(selenium):
    import shapely.geos

    assert shapely.geos.geos_version
    assert shapely.geos.geos_version_string
