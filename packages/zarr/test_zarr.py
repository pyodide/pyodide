from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["numpy", "numcodecs", "zarr"])
def test_zarr():
    from numcodecs import Blosc
    import numpy as np
    import zarr

    # basic test
    z = zarr.zeros((1000, 1000), chunks=(100, 100), dtype="i4")
    assert z.shape == (1000, 1000)

    # test assignment
    z[0, :] = np.arange(1000)
    assert z[0, 1] == 1

    # test saving and loading
    a1 = np.arange(10)
    zarr.save("/tmp/example.zarr", a1)
    a2 = zarr.load("/tmp/example.zarr")
    np.testing.assert_equal(a1, a2)

    # test compressor
    compressor = Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE)
    data = np.arange(10000, dtype="i4").reshape(100, 100)
    z = zarr.array(data, chunks=(10, 10), compressor=compressor)
    assert z.compressor == compressor
