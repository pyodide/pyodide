# https://github.com/iskandr/parakeet/blob/master/benchmarks/nd_local_maxima.py
# setup: import numpy as np ; shape = (3,2,3,2) ; x = np.arange(36, dtype=np.float64).reshape(*shape)  # noqa
# run: local_maxima(x)

# pythran export local_maxima(float [][][][])
import numpy as np


def wrap(pos, offset, bound):
    return (pos + offset) % bound


def clamp(pos, offset, bound):
    return min(bound - 1, max(0, pos + offset))


def reflect(pos, offset, bound):
    idx = pos + offset
    return min(2 * (bound - 1) - idx, max(idx, -idx))


def local_maxima(data, mode=wrap):
    wsize = data.shape
    result = np.ones(data.shape, bool)
    for pos in np.ndindex(data.shape):
        myval = data[pos]
        for offset in np.ndindex(wsize):
            neighbor_idx = tuple(mode(p, o - w // 2, w)
                                 for (p, o, w) in zip(pos, offset, wsize))
            result[pos] &= (data[neighbor_idx] <= myval)
    return result
