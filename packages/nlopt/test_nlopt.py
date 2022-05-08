from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(
    packages=["nlopt"],
    xfail_browsers={
        "chrome": "nlopt set_min_objective triggers a fatal runtime error in chrome 89 see #1493",
    },
)
def test_nlopt():
    import nlopt
    import numpy as np

    # objective function
    def f(x, grad):
        x0 = x[0]
        x1 = x[1]
        y = (
            67.8306620138889
            - 13.5689721666667 * x0
            - 3.83269458333333 * x1
            + 0.720841066666667 * x0**2
            + 0.3427605 * x0 * x1
            + 0.0640322916666664 * x1**2
        )

        grad[0] = 1.44168213333333 * x0 + 0.3427605 * x1 - 13.5689721666667
        grad[1] = 0.3427605 * x0 + 0.128064583333333 * x1 - 3.83269458333333

        return y

    # inequality constraint (constrained to be <= 0)
    def h(x, grad):
        x0 = x[0]
        x1 = x[1]
        z = (
            -3.72589930555515
            + 128.965158333333 * x0
            + 0.341479166666643 * x1
            - 0.19642666666667 * x0**2
            + 2.78692500000002 * x0 * x1
            - 0.0000104166666686543 * x1**2
            - 468.897287036862
        )

        grad[0] = -0.39285333333334 * x0 + 2.78692500000002 * x1 + 128.965158333333
        grad[1] = 2.78692500000002 * x0 - 2.08333333373086e-5 * x1 + 0.341479166666643

        return z

    opt = nlopt.opt(nlopt.LD_SLSQP, 2)
    opt.set_min_objective(f)

    opt.set_lower_bounds(np.array([2.5, 7]))
    opt.set_upper_bounds(np.array([7.5, 15]))

    opt.add_inequality_constraint(h)

    opt.set_ftol_rel(1.0e-6)

    x0 = np.array([5, 11])

    xopt = opt.optimize(x0)

    assert np.linalg.norm(xopt - np.array([2.746310775, 15.0])) < 1e-7
