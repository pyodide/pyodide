def test_zarr(selenium):
    selenium.load_package("zarr")
    selenium.run(
        r"""
import zarr
z = zarr.zeros((10000, 10000), chunks=(1000, 1000), dtype='i4')
    """
    )
