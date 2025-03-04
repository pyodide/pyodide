import blosc2
import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["blosc2"])
@pytest.mark.parametrize("data", [bytearray(7241), bytearray(7241) * 7])
def test_bytearray(selenium, data):
    cdata = blosc2.compress(data, typesize=1)
    uncomp = blosc2.decompress(cdata)
    assert data == uncomp


@run_in_pyodide(packages=["blosc2"])
@pytest.mark.parametrize("gil", [True, False])
@pytest.mark.parametrize(
    ("nbytes", "cparams", "dparams"),
    [
        (7, {"codec": blosc2.Codec.LZ4, "clevel": 6, "typesize": 1}, {}),
        (641091, {"typesize": 1}, {"nthreads": 4}),
        (136, {"typesize": 1}, {}),
        (1231, {"typesize": 4}, blosc2.dparams_dflts),
    ],
)
def test_compress2(selenium, nbytes, cparams, dparams, gil):
    blosc2.set_releasegil(gil)
    bytes_obj = b" " * nbytes
    c = blosc2.compress2(bytes_obj, **cparams)

    dest = bytearray(bytes_obj)
    blosc2.decompress2(c, dst=dest, **dparams)
    assert dest == bytes_obj

    dest2 = blosc2.decompress2(c, **dparams)
    assert dest2 == bytes_obj

    dest3 = bytearray(bytes_obj)
    blosc2.decompress2(np.array([c]), dst=dest3, **dparams)
    assert dest3 == bytes_obj


@run_in_pyodide(packages=["blosc2"])
@pytest.mark.parametrize("asarray", [True, False])
@pytest.mark.parametrize("typesize", [255, 256, 257, 261, 256 * 256])
@pytest.mark.parametrize("shape", [(1,), (3,), (10,), (2 * 10,), (2**8 - 1, 3)])
def test_large_typesize(selenium, shape, typesize, asarray):
    import numpy as np

    dtype = np.dtype([("f_001", "<i1", (typesize,)), ("f_002", "f4", (typesize,))])
    a = np.zeros(shape, dtype=dtype)
    if asarray:
        b = blosc2.asarray(a)
    else:
        b = blosc2.zeros(shape, dtype=dtype)
    assert np.array_equal(b[0], a[0])
