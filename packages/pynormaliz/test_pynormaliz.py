from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pynormaliz"])
def test_pynormaliz(selenium):
    import PyNormaliz_cpp

    ineq = [[0, 0, 1], [0, 1, 0], [1, 0, 0]]
    cone = PyNormaliz_cpp.NmzCone(["cone", ineq])
    PyNormaliz_cpp.NmzResult(cone, "HilbertBasis")
    cone2 = PyNormaliz_cpp.NmzResult(cone, "IntegerHull")
    PyNormaliz_cpp.NmzResult(cone2, "HilbertBasis")


@run_in_pyodide(packages=["pynormaliz"])
def test_pynormaliz(selenium):
    import PyNormaliz_cpp

    C = PyNormaliz_cpp.NmzCone(
        number_field=["a2-2", "a", "1.4+/-0.1"], cone=[[[1], [0, 1]], [[1], [-1]]]
    )
    PyNormaliz_cpp.NmzCompute(C, ["SupportHyperplanes"])
    PyNormaliz_cpp.NmzResult(C, "ExtremeRays")

    def rat_handler(list):
        return list[0] / list[1]

    PyNormaliz_cpp.NmzResult(
        C,
        "ExtremeRays",
        RationalHandler=rat_handler,
        NumberfieldElementHandler=tuple,
        VectorHandler=tuple,
        MatrixHandler=tuple,
    )
