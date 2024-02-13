from pyodide_build._f2c_fixes import (
    replay_f2c,
)


def _args_wrapper(func):
    """Convert function to take as input / return a string instead of a
    list of arguments

    Also sets dryrun=True
    """

    def _inner(line, *pargs):
        args = line.split()
        res = func(args, *pargs, dryrun=True)
        if hasattr(res, "__len__"):
            return " ".join(res)
        else:
            return res

    return _inner


f2c_wrap = _args_wrapper(replay_f2c)


def test_f2c():
    assert f2c_wrap("gfortran test.f") == "gcc test.c"
    assert f2c_wrap("gcc test.c") is None
    assert f2c_wrap("gfortran --version") is None
    assert (
        f2c_wrap("gfortran --shared -c test.o -o test.so")
        == "gcc --shared -c test.o -o test.so"
    )
