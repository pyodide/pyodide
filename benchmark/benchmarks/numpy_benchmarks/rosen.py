# setup: import numpy as np; r = np.arange(1000000, dtype=float)
# run: rosen(r)
import numpy as np

# pythran export rosen(float[])


def rosen(x):
    t0 = 100 * (x[1:] - x[:-1] ** 2) ** 2
    t1 = (1 - x[:-1]) ** 2
    return np.sum(t0 + t1)
