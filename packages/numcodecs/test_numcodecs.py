import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(
    chrome="test_numcodecs triggers a recursion error in chrome"
)
@run_in_pyodide(
    packages=["numcodecs", "numpy"],
)
def test_blosc(selenium_standalone):
    import array

    import numpy as np
    from numcodecs.blosc import Blosc
    from numcodecs.compat import ensure_bytes, ensure_ndarray
    from numcodecs.lz4 import LZ4
    from numcodecs.zstd import Zstd
    from numpy.testing import assert_array_almost_equal, assert_array_equal

    def compare_arrays(arr, res, precision=None):
        # ensure numpy array with matching dtype
        res = ensure_ndarray(res).view(arr.dtype)

        # convert to correct shape
        if arr.flags.f_contiguous:
            order = "F"
        else:
            order = "C"
        res = res.reshape(arr.shape, order=order)

        # exact compare
        if precision is None:
            assert_array_equal(arr, res)

        # fuzzy compare
        else:
            assert_array_almost_equal(arr, res, decimal=precision)

    def check_encode_decode(arr, codec, precision=None):

        # N.B., watch out here with blosc compressor, if the itemsize of
        # the source buffer is different then the results of encoding
        # (i.e., compression) may be different. Hence we *do not* require that
        # the results of encoding be identical for all possible inputs, rather
        # we just require that the results of the encode/decode round-trip can
        # be compared to the original array.

        # encoding should support any object exporting the buffer protocol

        # test encoding of numpy array
        enc = codec.encode(arr)
        dec = codec.decode(enc)
        compare_arrays(arr, dec, precision=precision)

        # test encoding of bytes
        buf = arr.tobytes(order="A")
        enc = codec.encode(buf)
        dec = codec.decode(enc)
        compare_arrays(arr, dec, precision=precision)

        # test encoding of bytearray
        buf = bytearray(arr.tobytes(order="A"))
        enc = codec.encode(buf)
        dec = codec.decode(enc)
        compare_arrays(arr, dec, precision=precision)

        # test encoding of array.array
        buf = array.array("b", arr.tobytes(order="A"))
        enc = codec.encode(buf)
        dec = codec.decode(enc)
        compare_arrays(arr, dec, precision=precision)

        # decoding should support any object exporting the buffer protocol,

        # setup
        enc_bytes = ensure_bytes(enc)

        # test decoding of raw bytes
        dec = codec.decode(enc_bytes)
        compare_arrays(arr, dec, precision=precision)

        # test decoding of bytearray
        dec = codec.decode(bytearray(enc_bytes))
        compare_arrays(arr, dec, precision=precision)

        # test decoding of array.array
        buf = array.array("b", enc_bytes)
        dec = codec.decode(buf)
        compare_arrays(arr, dec, precision=precision)

        # test decoding of numpy array
        buf = np.frombuffer(enc_bytes, dtype="u1")
        dec = codec.decode(buf)
        compare_arrays(arr, dec, precision=precision)

        # test decoding directly into numpy array
        out = np.empty_like(arr)
        codec.decode(enc_bytes, out=out)
        compare_arrays(arr, out, precision=precision)

        # test decoding directly into bytearray
        out = bytearray(arr.nbytes)
        codec.decode(enc_bytes, out=out)
        # noinspection PyTypeChecker
        compare_arrays(arr, out, precision=precision)

    # mix of dtypes: integer, float, bool, string
    # mix of shapes: 1D, 2D, 3D
    # mix of orders: C, F
    arrays = [
        np.arange(1000, dtype="i4"),
        np.linspace(1000, 1001, 1000, dtype="f8"),
        np.random.normal(loc=1000, scale=1, size=(100, 10)),
        np.random.randint(0, 2, size=1000, dtype=bool).reshape(100, 10, order="F"),
        np.random.choice([b"a", b"bb", b"ccc"], size=1000).reshape(10, 10, 10),
        np.random.randint(0, 2**60, size=1000, dtype="u8").view("M8[ns]"),
        np.random.randint(0, 2**60, size=1000, dtype="u8").view("m8[ns]"),
        np.random.randint(0, 2**25, size=1000, dtype="u8").view("M8[m]"),
        np.random.randint(0, 2**25, size=1000, dtype="u8").view("m8[m]"),
        np.random.randint(-(2**63), -(2**63) + 20, size=1000, dtype="i8").view(
            "M8[ns]"
        ),
        np.random.randint(-(2**63), -(2**63) + 20, size=1000, dtype="i8").view(
            "m8[ns]"
        ),
        np.random.randint(-(2**63), -(2**63) + 20, size=1000, dtype="i8").view(
            "M8[m]"
        ),
        np.random.randint(-(2**63), -(2**63) + 20, size=1000, dtype="i8").view(
            "m8[m]"
        ),
    ]

    codecs = [
        LZ4(),
        LZ4(acceleration=-1),
        LZ4(acceleration=10),
        Zstd(),
        Zstd(level=-1),
        Zstd(level=10),
        Blosc(shuffle=Blosc.SHUFFLE),
        Blosc(clevel=0, shuffle=Blosc.SHUFFLE),
        Blosc(cname="lz4", shuffle=Blosc.SHUFFLE),
        Blosc(cname="lz4", clevel=1, shuffle=Blosc.NOSHUFFLE),
        Blosc(cname="lz4", clevel=5, shuffle=Blosc.SHUFFLE),
        Blosc(cname="lz4", clevel=9, shuffle=Blosc.BITSHUFFLE),
        Blosc(cname="zlib", clevel=1, shuffle=0),
        Blosc(cname="zstd", clevel=1, shuffle=1),
        Blosc(cname="blosclz", clevel=1, shuffle=2),
        Blosc(shuffle=Blosc.SHUFFLE, blocksize=0),
        Blosc(shuffle=Blosc.SHUFFLE, blocksize=2**8),
        Blosc(cname="lz4", clevel=1, shuffle=Blosc.NOSHUFFLE, blocksize=2**8),
    ]
    for codec in codecs:
        for arr in arrays:
            check_encode_decode(arr, codec)
