from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["pyrtl"])
def test_pyrtl():
    import pyrtl

    # Calculate GCD of a and b
    a, b, begin = pyrtl.input_list("a/8 b/8 begin/1")
    gcd, done = pyrtl.output_list("gcd/8 done/1")

    x = pyrtl.Register(len(a))
    y = pyrtl.Register(len(b))

    with pyrtl.conditional_assignment:
        with begin:
            x.next |= a
            y.next |= b
        with x > y:
            x.next |= x - y
        with y > x:
            y.next |= y - x
        with pyrtl.otherwise:
            done |= True

    gcd <<= x

    sim = pyrtl.Simulation()
    sim.step(
        {
            "a": 56,
            "b": 42,
            "begin": 1,
        }
    )
    while sim.inspect("done") != 1:
        sim.step({"a": 0, "b": 0, "begin": 0})
    assert sim.inspect("gcd") == 14
