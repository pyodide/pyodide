# from: parakeet testbed
# setup: import numpy as np ; M, N = 512, 512 ; X = np.random.randn(M,N)
# run: harris(X)

# pythran export harris(float64[][])


def harris(X):
    m, n = X.shape
    dx = (X[1:, :] - X[:m - 1, :])[:, 1:]
    dy = (X[:, 1:] - X[:, :n - 1])[1:, :]

    #
    #   At each point we build a matrix
    #   of derivative products
    #   M =
    #   | A = dx^2     C = dx * dy |
    #   | C = dy * dx  B = dy * dy |
    #
    #   and the score at that point is:
    #      det(M) - k*trace(M)^2
    #
    A = dx * dx
    B = dy * dy
    C = dx * dy
    tr = A + B
    det = A * B - C * C
    k = 0.05
    return det - k * tr * tr
