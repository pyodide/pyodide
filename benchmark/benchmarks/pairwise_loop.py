# from: http://jakevdp.github.com/blog/2012/08/24/numba-vs-cython/
# setup: import numpy as np ; X = np.linspace(0,10,200).reshape(20,10)
# run: pairwise_loop(X)

# pythran export pairwise_loop(float [][])

import numpy as np


def pairwise_loop(X):
    M, N = X.shape
    D = np.empty((M, M))
    for i in range(M):
        for j in range(M):
            d = 0.0
            for k in range(N):
                tmp = X[i, k] - X[j, k]
                d += tmp * tmp
            D[i, j] = np.sqrt(d)
    return D
