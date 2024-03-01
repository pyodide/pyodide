from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["clarabel", "scipy", "numpy"])
def test_clarabel(selenium):
    import clarabel
    from scipy import sparse
    import numpy as np

    # Define problem data
    P = sparse.csc_matrix([[0., 0.], [0, 0]])
    P = sparse.triu(P).tocsc()

    q = np.array([-1., -4.])

    A = sparse.csc_matrix(
        [[1., -2.],        # <-- LHS of equality constraint (lower bound)
        [1.,  0.],        # <-- LHS of inequality constraint (upper bound)
        [0.,  1.],        # <-- LHS of inequality constraint (upper bound)
        [-1.,  0.],       # <-- LHS of inequality constraint (lower bound)
        [0., -1.]])       # <-- LHS of inequality constraint (lower bound)

    b = np.array([0., 1., 1., 1., 1.])

    cones = [clarabel.ZeroConeT(1), clarabel.NonnegativeConeT(4)]

    settings = clarabel.DefaultSettings()

    solver = clarabel.DefaultSolver(P, q, A, b, cones, settings)

    solution = solver.solve()
    assert solution.status == clarabel.SolverStatus.Solved