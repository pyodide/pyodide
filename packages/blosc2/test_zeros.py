#######################################################################
# Copyright (c) 2019-present, Blosc Development Team <blosc@blosc.org>
# All rights reserved.
#
# This source code is licensed under a BSD-style license (found in the
# LICENSE file in the root directory of this source tree)
#######################################################################

import math

import numpy as np
import pytest

import blosc2


@pytest.mark.parametrize(
    ("shape", "chunks", "blocks", "dtype", "cparams", "urlpath", "contiguous", "meta"),
    [
        (
            (100, 1230),
            (200, 100),
            (55, 3),
            np.int32,
            {"codec": blosc2.Codec.ZSTD, "clevel": 4, "use_dict": 0, "nthreads": 1},
            None,
            True,
            None,
        ),
        (
            (23, 34),
            (10, 10),
            (10, 10),
            np.float64,
            {"codec": blosc2.Codec.BLOSCLZ, "clevel": 8, "use_dict": False, "nthreads": 2},
            "zeros.b2nd",
            True,
            {"abc": 123456789, "2": [0, 1, 23]},
        ),
        (
            (80, 51, 60),
            (20, 10, 33),
            (6, 6, 26),
            np.bool_,
            {"codec": blosc2.Codec.LZ4, "clevel": 5, "use_dict": 1, "nthreads": 2},
            None,
            False,
            {"abc": 123, "2": [0, 1, 24]},
        ),
        (
            (2**31 - 1,),
            (2**30,),
            None,
            np.float32,
            {"codec": blosc2.Codec.LZ4, "clevel": 5, "nthreads": 2},
            None,
            False,
            None,
        ),
    ],
)
def test_zeros(shape, chunks, blocks, dtype, cparams, urlpath, contiguous, meta):
    blosc2.remove_urlpath(urlpath)

    dtype = np.dtype(dtype)
    if math.prod(chunks) * dtype.itemsize > blosc2.MAX_BUFFERSIZE:
        with pytest.raises(RuntimeError):
            _ = blosc2.zeros(
                shape,
                chunks=chunks,
                blocks=blocks,
                dtype=dtype,
                cparams=cparams,
                urlpath=urlpath,
                contiguous=contiguous,
                meta=meta,
            )
        return
    else:
        a = blosc2.zeros(
            shape,
            chunks=chunks,
            blocks=blocks,
            dtype=dtype,
            cparams=cparams,
            urlpath=urlpath,
            contiguous=contiguous,
            meta=meta,
        )

    b = np.zeros(shape=shape, dtype=dtype)
    assert np.array_equal(a[:], b)

    if meta is not None:
        for metalayer in meta:
            m = a.schunk.meta[metalayer]
            assert m == meta[metalayer]

    blosc2.remove_urlpath(urlpath)


@pytest.mark.parametrize(
    ("shape", "dtype"),
    [
        (100, np.uint8),
        ((100, 1230), np.uint8),
        ((234, 125), np.int32),
        ((80, 51, 60), np.bool_),
        ((400, 399, 401), np.float64),
    ],
)
def test_zeros_minimal(shape, dtype):
    a = blosc2.zeros(shape, dtype=dtype)

    b = np.zeros(shape=shape, dtype=dtype)
    assert np.array_equal(a[:], b)

    dtype = np.dtype(dtype)
    assert shape in (a.shape, a.shape[0])
    assert a.chunks is not None
    assert a.blocks is not None
    assert all(c >= b for c, b in zip(a.chunks, a.blocks, strict=False))
    assert a.dtype == dtype
    assert a.schunk.typesize == dtype.itemsize


@pytest.mark.parametrize("asarray", [True, False])
@pytest.mark.parametrize("typesize", [255, 256, 257, 261, 256 * 256])
@pytest.mark.parametrize("shape", [(1,), (3,), (10,), (2 * 10,), (2**8 - 1, 3)])
def test_large_typesize(shape, typesize, asarray):
    dtype = np.dtype([("f_001", "<i1", (typesize,)), ("f_002", "f4", (typesize,))])
    a = np.zeros(shape, dtype=dtype)
    if asarray:
        b = blosc2.asarray(a)
    else:
        b = blosc2.zeros(shape, dtype=dtype)
    assert np.array_equal(b[0], a[0])
