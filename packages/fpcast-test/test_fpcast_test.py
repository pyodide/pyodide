import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.requires_dynamic_linking
@run_in_pyodide(packages=["fpcast-test"])
def test_fpcasts(selenium):
    import fpcast_test

    fpcast_test.noargs0()
    fpcast_test.noargs1()
    fpcast_test.noargs2()
    fpcast_test.noargs3()

    fpcast_test.varargs0()
    fpcast_test.varargs1()
    fpcast_test.varargs2()
    fpcast_test.varargs3()

    fpcast_test.kwargs0()
    fpcast_test.kwargs1()
    fpcast_test.kwargs2()
    fpcast_test.kwargs3()

    fpcast_test.Callable0()()
    fpcast_test.Callable1()()
    fpcast_test.Callable2()()
    fpcast_test.Callable3()()

    t = fpcast_test.TestType()
    t.noargs0()
    t.noargs1()
    t.noargs2()
    t.noargs3()

    t.varargs0()
    t.varargs1()
    t.varargs2()
    t.varargs3()

    t.kwargs0()
    t.kwargs1()
    t.kwargs2()
    t.kwargs3()

    t.getset0  # noqa: B018
    t.getset1  # noqa: B018
    t.getset1 = 5
