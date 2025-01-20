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

    assert np.isclose(result.full()[0, 0], 3, atol=1e-6)


######################################################################

# CasADi integrator tests, using the damped harmonic oscillator and the
# bouncing balls as examples. The tests are run for both CVODES and IDAS.


@run_in_pyodide(packages=["casadi", "numpy"])
@pytest.mark.parametrize("integrator_type", ["cvodes", "idas"])
def test_harmonic_oscillator(selenium, integrator_type):
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
        "max_num_steps": 10000,  # max steps
    }

    F = ca.integrator("F", integrator_type, dae, 0, 1, opts)

    # Set initial conditions: x(0) = 1, v(0) = 0
    r = F(x0=[1, 0])

    # exact analytical solution for the damped harmonic oscillator
    def exact_solution(t, x0, v0):
        # damped natural frequency
        wd = omega * np.sqrt(1 - zeta**2)
        # initial amplitude
        A = np.sqrt(x0**2 + ((v0 + zeta * omega * x0) / wd) ** 2)
        phi = np.arctan((v0 + zeta * omega * x0) / (wd * x0))

        x = A * np.exp(-zeta * omega * t) * np.cos(wd * t - phi)
        v = (
            -A
            * np.exp(-zeta * omega * t)
            * (zeta * omega * np.cos(wd * t - phi) + wd * np.sin(wd * t - phi))
        )

        return x, v

    t = 1  # Solution at t equals 1
    expected_x, expected_v = exact_solution(t, 1, 0)

    assert np.isclose(r["xf"][0].full()[0, 0], expected_x, atol=1e-8, rtol=1e-6)
    assert np.isclose(r["xf"][1].full()[0, 0], expected_v, atol=1e-8, rtol=1e-6)

    # probably test with custom time horizon too
    t_custom = 2
    F_custom = ca.integrator("F_custom", integrator_type, dae, 0, t_custom, opts)
    r_custom = F_custom(x0=[1, 0])

    expected_x_custom, expected_v_custom = exact_solution(t_custom, 1, 0)

    assert np.isclose(
        r_custom["xf"][0].full()[0, 0], expected_x_custom, atol=1e-6, rtol=1e-6
    )
    assert np.isclose(
        r_custom["xf"][1].full()[0, 0], expected_v_custom, atol=1e-6, rtol=1e-6
    )

    # verify that the results are indeed different
    assert not np.isclose(
        r["xf"][0].full()[0, 0], r_custom["xf"][0].full()[0, 0], atol=1e-6, rtol=1e-6
    )


@run_in_pyodide(packages=["casadi", "numpy"])
@pytest.mark.parametrize("integrator_type", ["cvodes", "idas"])
def test_bouncing_ball(selenium, integrator_type):
    import casadi as ca

    # Parameters
    g = 9.81  # Gravity (m/s^2)
    e = 0.8  # Coefficient of restitution
    h0 = 10  # Initial height (m)
    v0 = 0  # Initial velocity (m/s)

    # state variables
    s = ca.SX.sym("s", 2)  # s[0] is height, s[1] is velocity

    # add ODE right hand side
    ode = ca.vertcat(s[1], -g)

    # create integrator
    opts = {"abstol": 1e-8, "reltol": 1e-8, "max_num_steps": 1000}
    integrator = ca.integrator(
        "integrator", integrator_type, {"x": s, "ode": ode}, opts
    )

    # simulating a bouncing ball
    sim_time = 2.0
    num_steps = 20
    dt = sim_time / num_steps

    t_log = [0.0]
    h_log = [h0]
    v_log = [v0]

    s_current = ca.DM([h0, v0])
    t_current = 0.0

    for _ in range(num_steps):
        # integrate for one step
        res = integrator(x0=s_current, p=dt)
        s_end = res["xf"]
        # check if the ball passed through the ground
        if s_end[0] < 0:
            # some simple bounce handling
            s_end[0] = abs(s_end[0])  # reflect position
            s_end[1] = -e * s_end[1]  # apply coefficient of restitution

        t_current += dt
        t_log.append(t_current)
        h_log.append(s_end[0])
        v_log.append(s_end[1])

        s_current = s_end

    # adding some basic verifications
    assert len(t_log) == num_steps + 1, (
        f"Expected {num_steps + 1} time steps, got {len(t_log)}"
    )
    assert all(h >= 0 for h in h_log), "Height should never be negative"
    assert abs(h_log[0] - h0) < 1e-6, "Initial height should match h0"
    assert abs(v_log[0] - v0) < 1e-6, "Initial velocity should match v0"

    max_heights = [max(h_log[i:]) for i in range(0, len(h_log), 5)]
    assert all(
        max_heights[i] >= max_heights[i + 1] for i in range(len(max_heights) - 1)
    ), "Maximum height should not increase over time"


######################################################################


@pytest.mark.parametrize(
    "interp_type, expected_result", [("linear", 6.5), ("bspline", 6.25)]
)
@run_in_pyodide(packages=["casadi", "numpy"])
def test_interpolant(selenium, interp_type, expected_result):
    import casadi as ca
    import numpy as np

    x = [0, 1, 2, 3, 4, 5]
    y = [0, 1, 4, 9, 16, 25]
    F = ca.interpolant("F", interp_type, [x], y)

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
