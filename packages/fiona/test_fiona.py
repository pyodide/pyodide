import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["fiona"])
def test_supported_drivers(selenium):
    import fiona

    assert fiona.driver_count() > 0


@run_in_pyodide(packages=["fiona"])
def test_geometry_collection_round_trip(selenium):
    from fiona._geometry import geometryRT
    geom = {
        "type": "GeometryCollection",
        "geometries": [
            {"type": "Point", "coordinates": (0.0, 0.0)},
            {"type": "LineString", "coordinates": [(0.0, 0.0), (1.0, 1.0)]},
        ],
    }

    result = geometryRT(geom)
    assert len(result["geometries"]) == 2
    assert [g["type"] for g in result["geometries"]] == ["Point", "LineString"]
