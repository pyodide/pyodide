import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(firefox="slow")
@run_in_pyodide(packages=["clarabel", "scipy", "numpy"])
def test_clarabel(selenium):
    import clarabel
    import numpy as np
    from scipy import sparse

    # Define problem data
    P = sparse.csc_matrix([[0.0, 0.0], [0, 0]])
    P = sparse.triu(P).tocsc()

    q = np.array([-1.0, -4.0])

    A = sparse.csc_matrix(
        [
            [1.0, -2.0],  # <-- LHS of equality constraint (lower bound)
            [1.0, 0.0],  # <-- LHS of inequality constraint (upper bound)
            [0.0, 1.0],  # <-- LHS of inequality constraint (upper bound)
            [-1.0, 0.0],  # <-- LHS of inequality constraint (lower bound)
            [0.0, -1.0],
        ]
    )  # <-- LHS of inequality constraint (lower bound)

    b = np.array([0.0, 1.0, 1.0, 1.0, 1.0])

    cones = [clarabel.ZeroConeT(1), clarabel.NonnegativeConeT(4)]

    settings = clarabel.DefaultSettings()

    solver = clarabel.DefaultSolver(P, q, A, b, cones, settings)

    solution = solver.solve()
    assert solution.status == clarabel.SolverStatus.Solved
