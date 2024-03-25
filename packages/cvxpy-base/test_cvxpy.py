import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(firefox="slow")
@run_in_pyodide(packages=["cvxpy-base"])
def test_cvxpy_clarabel(selenium):
    import cvxpy as cp

    P = [[3.0, 1.0, -1.0], [1.0, 4.0, 2.0], [-1.0, 2.0, 5.0]]

    q = [1.0, 2.0, -3.0]

    # Create optimization variables
    x = cp.Variable(3)

    constraints = [x[0] + x[1] - x[2] == 1, x[1] <= 2, x[2] <= 2, cp.SOC(x[0], x[1:])]

    # Form objective.
    obj = cp.Minimize(0.5 * cp.quad_form(x, P) + q @ x)

    # Form and solve problem.
    prob = cp.Problem(obj, constraints)
    prob.solve(solver=cp.CLARABEL)
    assert prob.status == cp.OPTIMAL


@run_in_pyodide(packages=["cvxpy-base"])
def test_cvxpy_scipy(selenium):
    import cvxpy as cp

    q = [1.0, 2.0, -3.0]

    # Create optimization variables
    x = cp.Variable(3)

    constraints = [
        x[0] + x[1] - x[2] == 1,
        x[1] >= 2,
        x[2] <= 2,
    ]

    # Form objective.
    obj = cp.Minimize(q @ x)

    # Form and solve problem.
    prob = cp.Problem(obj, constraints)
    prob.solve(solver=cp.SCIPY)
    assert prob.status == cp.OPTIMAL
