from pyodide_test_runner import run_in_pyodide

@run_in_pyodide(
    packages=[
        "rebound",
    ]
)
def test_integrate(selenium):
    import rebound
    import numpy

    sim = rebound.Simulation()
    sim.add(m=1)
    sim.add(m=1e-3, a=1)
    sim.add(m=1e-3, a=2)
    sim.integrate(10)

    assert numpy.fabs(sim.t - 10.0) < 1e-10, "Orbit integration not working"
    return None
