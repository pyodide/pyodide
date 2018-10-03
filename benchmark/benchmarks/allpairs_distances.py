# setup: import numpy as np ; N = 50 ; X, Y = np.random.randn(100,N), np.random.randn(40,N)  # noqa
# run: allpairs_distances(X, Y)

# pythran export allpairs_distances(float64[][], float64[][])
import numpy as np


def allpairs_distances(A, B):
    """ This returns the euclidean distances squared
    dist2(x, y) = dot(x, x) - 2 * dot(x, y) + dot(y, y)
    """
    A2 = np.einsum('ij,ij->i', A, A)
    B2 = np.einsum('ij,ij->i', B, B)
    return A2[:, None] + B2[None, :] - 2 * np.dot(A, B.T)
