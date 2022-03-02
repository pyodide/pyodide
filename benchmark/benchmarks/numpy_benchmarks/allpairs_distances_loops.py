# setup: import numpy as np ; N = 50 ; X, Y = np.random.randn(30,N), np.random.randn(20,N)  # noqa
# run: allpairs_distances_loops(X, Y)

# pythran export allpairs_distances_loops(float64[][], float64[][])
import numpy as np


def allpairs_distances_loops(X, Y):
    result = np.zeros((X.shape[0], Y.shape[0]), X.dtype)
    for i in range(X.shape[0]):
        for j in range(Y.shape[0]):
            result[i, j] = np.sum((X[i, :] - Y[j, :]) ** 2)
    return result
