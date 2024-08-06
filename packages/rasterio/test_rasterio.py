from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["rasterio"])
def test_drivers(selenium):
    import rasterio
    from rasterio._env import driver_count

    with rasterio.Env() as m:
        assert driver_count() > 0
        assert type(m) == rasterio.Env
    assert driver_count() > 0


@run_in_pyodide(packages=["rasterio"])
def test_open(selenium):
    """
    Test copied from conda-forge recipe
    """

    import numpy
    import rasterio
    import rasterio.env
    from rasterio.features import rasterize
    from rasterio.transform import IDENTITY

    rows = cols = 10
    geometry = {
        "type": "Polygon",
        "coordinates": [[(2, 2), (2, 4.25), (4.25, 4.25), (4.25, 2), (2, 2)]],
    }

    with rasterio.Env():
        result = rasterize([geometry], out_shape=(rows, cols))
        with rasterio.open(
            "test.tif",
            "w",
            driver="GTiff",
            width=cols,
            height=rows,
            count=1,
            dtype=numpy.uint8,
            nodata=0,
            transform=IDENTITY,
            crs={"init": "EPSG:4326"},
        ) as out:
            out.write_band(1, result.astype(numpy.uint8))

    assert out.name == "test.tif"


@run_in_pyodide(packages=["rasterio"])
def test_affine(selenium):
    import numpy as np
    from rasterio.transform import Affine

    x = np.linspace(-4.0, 4.0, 240)
    y = np.linspace(-3.0, 3.0, 180)

    res = (x[-1] - x[0]) / 240.0
    affine = Affine(
        0.033333333333333333,
        0.0,
        -4.0166666666666666,
        0.0,
        0.033333333333333333,
        -3.0166666666666666,
    )

    transform = Affine.translation(x[0] - res / 2, y[0] - res / 2) * Affine.scale(
        res, res
    )
    assert affine == transform
