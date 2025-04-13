from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["python_solvespace"])
def test_regex(selenium):
    from python_solvespace import ResultFlag, SolverSystem

    sys = SolverSystem()
    wp = sys.create_2d_base()
    p0 = sys.add_point_2d(0, 0, wp)
    sys.dragged(p0, wp)
    p1 = sys.add_point_2d(90, 0, wp)
    sys.dragged(p1, wp)
    line0 = sys.add_line_2d(p0, p1, wp)
    p2 = sys.add_point_2d(20, 20, wp)
    p3 = sys.add_point_2d(0, 10, wp)
    p4 = sys.add_point_2d(30, 20, wp)
    sys.distance(p2, p3, 40, wp)
    sys.distance(p2, p4, 40, wp)
    sys.distance(p3, p4, 70, wp)
    sys.distance(p0, p3, 35, wp)
    sys.distance(p1, p4, 70, wp)
    line1 = sys.add_line_2d(p0, p3, wp)
    sys.angle(line0, line1, 45, wp)
    result_flag = sys.solve()
    assert result_flag == ResultFlag.OKAY
