import pytest
from pyodide_test_runner import run_in_pyodide


@pytest.mark.driver_timeout(40)
@run_in_pyodide(packages=["scipy,sparseqr"])
def test_scipy_linalg(selenium):
    import numpy
    import scipy.sparse.linalg
    import sparseqr
    from numpy.testing import assert_allclose

    # QR decompose a sparse matrix M such that  Q R = M E
    #
    M = scipy.sparse.rand(10, 10, density=0.1)
    Q, R, E, rank = sparseqr.qr(M)
    print(
        abs(Q * R - M * sparseqr.permutation_vector_to_matrix(E)).sum()
    )  # should be approximately zero

    b = numpy.random.random(10)
    v = Q.dot(R.dot(b))
    w = M.dot(sparseqr.permutation_vector_to_matrix(E).dot(b))

    assert_allclose(res, np.identity(N), rtol=1e-07, atol=1e-9)

    # Solve many linear systems "M x = b for b in columns(B)"
    #
    B = scipy.sparse.rand(
        10, 5, density=0.1
    )  # many RHS, sparse (could also have just one RHS with shape (10,))
    x = sparseqr.solve(M, B, tolerance=0)

    # Solve an overdetermined linear system  A x = b  in the least-squares sense
    #
    # The same routine also works for the usual non-overdetermined case.
    #
    A = scipy.sparse.rand(20, 10, density=0.1)  # 20 equations, 10 unknowns
    b = numpy.random.random(
        20
    )  # one RHS, dense, but could also have many (in shape (20,k))
    x = sparseqr.solve(A, b, tolerance=0)

    # Solve a linear system  M x = B  via QR decomposition
    #
    # This approach is slow due to the explicit construction of Q, but may be
    # useful if a large number of systems need to be solved with the same M.
    #
    M = scipy.sparse.rand(10, 10, density=0.1)
    Q, R, E, rank = sparseqr.qr(M)
    r = rank  # r could be min(M.shape) if M is full-rank

    # The system is only solvable if the lower part of Q.T @ B is all zero:
    print(
        "System is solvable if this is zero:", abs(((Q.tocsc()[:, r:]).T).dot(B)).sum()
    )

    # Systems with large non-square matrices can benefit from "economy" decomposition.
    M = scipy.sparse.rand(20, 5, density=0.1)
    B = scipy.sparse.rand(20, 5, density=0.1)
    Q, R, E, rank = sparseqr.qr(M)
    print("Q shape:", Q.shape)  # Q shape: (20, 20)
    print("R shape:", R.shape)  # R shape: (20, 5)
    Q, R, E, rank = sparseqr.qr(M, economy=True)
    print("Q shape:", Q.shape)  # Q shape: (20, 5)
    print("R shape:", R.shape)  # R shape: (5, 5)

    # Use CSC format for fast indexing of columns.
    R = R.tocsc()[:r, :r]
    Q = Q.tocsc()[:, :r]
    QB = (
        (Q.T).dot(B).tocsc()
    )  # for best performance, spsolve() wants the RHS to be in CSC format.
    result = scipy.sparse.linalg.spsolve(R, QB)

    # Recover a solution (as a dense array):
    x = numpy.zeros((M.shape[1], B.shape[1]), dtype=result.dtype)
    x[:r] = result.todense()
    x[E] = x.copy()

    # Recover a solution (as a sparse matrix):
    x = scipy.sparse.vstack(
        (
            result.tocoo(),
            scipy.sparse.coo_matrix(
                (M.shape[1] - rank, B.shape[1]), dtype=result.dtype
            ),
        )
    )
    x.row = E[x.row]
