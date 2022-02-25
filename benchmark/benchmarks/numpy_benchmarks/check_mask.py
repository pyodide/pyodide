# setup: n=100 ; import numpy; db = numpy.random.randint(2, size=(n, 4), dtype='bool')  # noqa
# run: check_mask(db)
# from:
# http://stackoverflow.com/questions/34500913/numba-slower-for-numpy-bitwise-and-on-boolean-arrays

# pythran export check_mask(bool[][])
import numpy as np


def check_mask(db, mask=[1, 0, 1]):
    out = np.zeros(db.shape[0], dtype=bool)
    for idx, line in enumerate(db):
        target, vector = line[0], line[1:]
        if (mask == np.bitwise_and(mask, vector)).all():
            if target == 1:
                out[idx] = 1
    return out
