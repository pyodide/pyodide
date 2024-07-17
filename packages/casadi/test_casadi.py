import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["casadi"])
def test_symbolic_variable(selenium):
    import casadi as ca

    x = ca.SX.sym("x")
    assert isinstance(x, ca.SX)
    assert x.name() == "x"


@run_in_pyodide(packages=["casadi", "numpy"])
def test_basic_casadi_function_eval(selenium):
    import casadi as ca
    import numpy as np

    x = ca.MX.sym("x")
    y = ca.MX.sym("y")
    f = ca.Function("f", [x, y], [x**2 + y**2])

    assert np.allclose(f(1, 2).full(), np.array([5]))
    assert np.allclose(f(3, 4).full(), np.array([25]))
    assert np.allclose(f(5, 6).full(), np.array([61]))


# IPOPT not available because compiled with -DWITH_IPOPT=OFF
# by default for size reasons. This can be changed by setting
# -DWITH_IPOPT=ON in the future, but it requires IPOPT to be
# built beforehand.
@pytest.mark.skip(reason="IPOPT not available for now")
@run_in_pyodide(packages=["casadi", "numpy"])
def test_simple_optimization(selenium):
    import casadi as ca
    import numpy as np

    opti = ca.Opti()
    x = opti.variable()
    y = opti.variable()
    opti.minimize((x - 1) ** 2 + (y - 2) ** 2)
    opti.solver("ipopt")
    sol = opti.solve()
    assert np.allclose(sol.value(x), 1.0, atol=1e-6)
    assert np.allclose(sol.value(y), 2.0, atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
def test_matrix_operations(selenium):
    import casadi as ca
    import numpy as np

    A = ca.DM([[1, 2], [3, 4]])
    B = ca.DM([[5, 6], [7, 8]])
    C = A @ B
    assert np.allclose(C.full(), np.array([[19, 22], [43, 50]]))


@run_in_pyodide(packages=["casadi", "numpy"])
def test_basic_integration(selenium):
    import casadi as ca
    import numpy as np

    t = ca.MX.sym("t")
    x = ca.MX.sym("x")
    ode = {"t": t, "x": x, "ode": -x}
    opts = {"tf": 1.0}
    F = ca.integrator("F", "cvodes", ode, opts)
    result = F(x0=1)
    assert np.allclose(result["xf"].full(), np.array([np.exp(-1)]), atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
def test_basic_rootfinder(selenium):
    import casadi as ca
    import numpy as np

    x = ca.MX.sym("x")
    p = ca.MX.sym("p")
    f = ca.Function("f", [x, p], [x**2 - p])

    # create a root finder with Newton's method
    opts = {
        "implicit_input": 0,
        "implicit_output": 0,
        "linear_solver": "csparse",  # Use sparse linear solver
        "max_iter": 100,  # Set maximum iterations
        "abstol": 1e-6,  # Set absolute tolerance
    }
    rf = ca.rootfinder("rf", "newton", f, opts)

    # solve for the square root of 9, with initial guess 2
    initial_guess = 2
    result = rf(initial_guess, 9)

    print(result)  # TODO: remove, added for debugging
    assert np.isclose(result.full()[0, 0], 3, atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
@pytest.mark.parametrize("integrator_type", ["cvodes", "idas"])
def test_casadi_integrator(selenium, integrator_type):
    import casadi as ca
    import numpy as np

    # define a damped harmonic oscillator:
    # d^2x/dt^2 + 2*zeta*omega*dx/dt + omega^2*x = 0
    x = ca.SX.sym("x")
    v = ca.SX.sym("v")
    omega = 2 * np.pi  # natural frequency
    zeta = 0.1  # damping ratio

    dae = {
        "x": ca.vertcat(x, v),
        "ode": ca.vertcat(v, -(omega**2) * x - 2 * zeta * omega * v),
    }
    opts = {
        "abstol": 1e-10,  # Absolute tolerance
        "reltol": 1e-10,  # Relative tolerance
        "max_num_steps": 100000,  # Maximum number of steps the integrator can take
    }

    F = ca.integrator("F", integrator_type, dae, 0, 1, opts)

    # Set initial conditions: x(0) = 1, v(0) = 0
    r = F(x0=[1, 0])

    # exact analytical solution for the damped harmonic oscillator
    def exact_solution(t):
        # damped natural frequency
        wd = omega * np.sqrt(1 - zeta**2)
        # initial amplitude
        A = 1
        phi = np.arctan(-zeta / np.sqrt(1 - zeta**2))

        # return A * np.exp(-zeta*omega*t) * (np.cos(wd * t) + zeta/np.sqrt(1 - zeta**2) * np.sin(wd*t))
        return A * np.exp(-zeta * omega * t) * np.cos(wd * t - phi)

    expected_x = exact_solution(1)  # Solution at t equals 1
    assert np.isclose(r["xf"][0].full()[0, 0], expected_x, atol=1e-6, rtol=1e-6)

    # probably test with custom time horizon too
    F_custom = ca.integrator("F_custom", integrator_type, dae, 0, 2, opts)
    r_custom = F_custom(x0=[1, 0])

    expected_x_custom = exact_solution(2)  # Solution at t equals 2
    assert np.isclose(
        r_custom["xf"][0].full()[0, 0], expected_x_custom, atol=1e-6, rtol=1e-6
    )

    # verify that the results are indeed different
    assert not np.isclose(
        r["xf"][0].full()[0, 0], r_custom["xf"][0].full()[0, 0], atol=1e-6, rtol=1e-6
    )


@pytest.mark.parametrize(
    "interp_type, expected_result", [("linear", 6.5), ("bspline", 6.25)]
)
@run_in_pyodide(packages=["casadi", "numpy"])
def test_interpolant(selenium, interp_type, expected_result):
    import casadi
    import numpy as np

    x = [0, 1, 2, 3, 4, 5]
    y = [0, 1, 4, 9, 16, 25]
    F = casadi.interpolant("F", interp_type, [x], y)

    test_x = 2.5
    result = F(test_x)
    assert np.isclose(result, expected_result, atol=1e-6)

    # Additiomal test points at edges
    assert np.isclose(F(0), 0, atol=1e-6)
    assert np.isclose(F(1), 1, atol=1e-6)
    assert np.isclose(F(5), 25, atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
def test_jacobian(selenium):
    import casadi as ca
    import numpy as np

    x = ca.MX.sym("x", 2)
    f = ca.Function("f", [x], [ca.vertcat(x[0] ** 2 + x[1] ** 2, x[0] * x[1])])

    # compute Jacobian symbolically
    J_sym = ca.jacobian(f(x), x)
    J = ca.Function("J", [x], [J_sym])

    result = J([3, 4])
    expected_jac = np.array([[6, 8], [4, 3]])

    assert np.allclose(result.full(), expected_jac, atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
def test_ode_rk4(selenium):
    import casadi as ca
    import numpy as np

    # use a simple ODE: dx/dt = -x
    x = ca.MX.sym("x")
    t = ca.MX.sym("t")
    ode = {"x": x, "t": t, "ode": -x}

    # create an integrator using RK4 (which doesn't require CVODES)
    F = ca.integrator("F", "rk", ode, {"t0": 0, "tf": 1})

    result = F(x0=1)
    expected = np.exp(-1)
    assert np.isclose(result["xf"].full()[0], expected, rtol=1e-6, atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
def test_forward_sensitivity(selenium):
    import casadi as ca
    import numpy as np

    x = ca.SX.sym("x", 2)
    p = ca.SX.sym("p")

    f = (x[0] - 2) ** 2 + (x[1] - p) ** 2

    F = ca.Function("F", [x, p], [f])

    # Compute Jacobian with respect to p
    J = ca.Function("J", [x, p], [ca.jacobian(F(x, p), p)])

    x_nom = [1, 1]
    p_nom = 1
    sens = J(x_nom, p_nom)

    # The sensitivity should be 2*(x[1] - p) = 2*(1 - 1) = 0
    assert np.isclose(sens.full()[0, 0], 0, atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
def test_adjoint_sensitivity(selenium):
    import casadi as ca
    import numpy as np

    x = ca.SX.sym("x", 2)
    p = ca.SX.sym("p")

    f = (x[0] - 2) ** 2 + (x[1] - p) ** 2

    F = ca.Function("F", [x, p], [f])

    # Compute gradient with respect to all inputs
    G = ca.Function("G", [x, p], [ca.gradient(F(x, p), ca.vertcat(x, p))])

    x_nom = [1, 1]
    p_nom = 1
    sens = G(x_nom, p_nom)

    expected = [2 * (1 - 2), 2 * (1 - 1), -2 * (1 - 1)]
    assert np.allclose(sens.full().flatten(), expected, atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
def test_gradient_computation(selenium):
    import casadi as ca
    import numpy as np

    x = ca.SX.sym("x", 2)
    f = x[0] ** 2 + x[1] ** 2

    F = ca.Function("F", [x], [f])

    # Compute gradient
    G = ca.Function("G", [x], [ca.gradient(F(x), x)])

    x_nom = [1, 2]
    grad = G(x_nom)

    expected = [2 * 1, 2 * 2]
    assert np.allclose(grad.full().flatten(), expected, atol=1e-6)


@run_in_pyodide(packages=["casadi", "numpy"])
def test_hessian_computation(selenium):
    import casadi as ca
    import numpy as np

    x = ca.SX.sym("x", 2)

    f = x[0] ** 2 + x[1] ** 2

    F = ca.Function("F", [x], [f])

    # Compute Hessian of the function
    H = ca.Function("H", [x], [ca.hessian(F(x), x)[0]])

    x_nom = [1, 2]
    hess = H(x_nom)

    expected = [[2, 0], [0, 2]]
    assert np.allclose(hess.full(), expected, atol=1e-6)
