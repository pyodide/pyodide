from dataclasses import dataclass

import pytest

from pyodide_build.pywasmcross import replay_command  # noqa: E402
from pyodide_build.pywasmcross import replay_f2c  # noqa: E402
from pyodide_build.pywasmcross import environment_substitute_args


@dataclass
class BuildArgs:
    """An object to hold build arguments"""

    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    replace_libs: str = ""
    host_install_dir: str = ""
    target_install_dir: str = ""


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


replay_command_wrap = _args_wrapper(replay_command)
f2c_wrap = _args_wrapper(replay_f2c)


def test_handle_command():
    args = BuildArgs()
    assert replay_command_wrap("gcc -print-multiarch", args) is None
    assert replay_command_wrap("gcc test.c", args) == "emcc test.c"
    assert (
        replay_command_wrap("gcc -shared -c test.o -o test.so", args)
        == "emcc -c test.o -o test.so"
    )

    # check cxxflags injection and cpp detection
    args = BuildArgs(
        cflags="-I./lib2",
        cxxflags="-std=c++11",
        ldflags="-lm",
    )
    assert (
        replay_command_wrap("gcc -I./lib1 test.cpp -o test.o", args)
        == "em++ -I./lib2 -std=c++11 -I./lib1 test.cpp -o test.o"
    )

    # check ldflags injection
    args = BuildArgs(
        cflags="",
        cxxflags="",
        ldflags="-lm",
        host_install_dir="",
        replace_libs="",
        target_install_dir="",
    )
    assert (
        replay_command_wrap("gcc -shared -c test.o -o test.so", args)
        == "emcc -lm -c test.o -o test.so"
    )

    # check library replacement and removal of double libraries
    args = BuildArgs(
        replace_libs="bob=fred",
    )
    assert (
        replay_command_wrap("gcc -shared test.o -lbob -ljim -ljim -o test.so", args)
        == "emcc test.o -lfred -ljim -o test.so"
    )

    # compilation checks in numpy
    assert replay_command_wrap("gcc /usr/file.c", args) is None


def test_handle_command_ldflags():
    # Make sure to remove unsupported link flags for wasm-ld

    args = BuildArgs()
    assert (
        replay_command_wrap(
            "gcc -Wl,--strip-all,--as-needed -Wl,--sort-common,-z,now,-Bsymbolic-functions -shared -c test.o -o test.so",
            args,
        )
        == "emcc -Wl,-z,now -c test.o -o test.so"
    )


@pytest.mark.parametrize(
    "in_ext, out_ext, executable, flag_name",
    [
        (".c", ".o", "emcc", "cflags"),
        (".cpp", ".o", "em++", "cxxflags"),
        (".c", ".so", "emcc", "ldflags"),
    ],
)
def test_handle_command_optflags(in_ext, out_ext, executable, flag_name):
    # Make sure that when multiple optflags are present those in cflags,
    # cxxflags, or ldflags has priority

    args = BuildArgs(**{flag_name: "-Oz"})
    assert (
        replay_command_wrap(f"gcc -O3 test.{in_ext} -o test.{out_ext}", args)
        == f"{executable} -Oz test.{in_ext} -o test.{out_ext}"
    )


def test_f2c():
    assert f2c_wrap("gfortran test.f") == "gcc test.c"
    assert f2c_wrap("gcc test.c") is None
    assert f2c_wrap("gfortran --version") is None
    assert (
        f2c_wrap("gfortran --shared -c test.o -o test.so")
        == "gcc --shared -c test.o -o test.so"
    )


def test_conda_unsupported_args():
    # Check that compile arguments that are not suported by emcc and are sometimes
    # used in conda are removed.
    args = BuildArgs()
    assert replay_command_wrap(
        "gcc -shared -c test.o -B /compiler_compat -o test.so", args
    ) == ("emcc -c test.o -o test.so")

    assert replay_command_wrap(
        "gcc -shared -c test.o -Wl,--sysroot=/ -o test.so", args
    ) == ("emcc -c test.o -o test.so")


def test_environment_var_substitution(monkeypatch):
    monkeypatch.setenv("PYODIDE_BASE", "pyodide_build_dir")
    monkeypatch.setenv("BOB", "Robert Mc Roberts")
    monkeypatch.setenv("FRED", "Frederick F. Freddertson Esq.")
    monkeypatch.setenv("JIM", "James Ignatius Morrison:Jimmy")
    args = environment_substitute_args(
        {
            "ldflags": '"-l$(PYODIDE_BASE)"',
            "cxxflags": "$(BOB)",
            "cflags": "$(FRED)",
            "replace_libs": "$(JIM)",
        }
    )
    assert (
        args["cflags"] == "Frederick F. Freddertson Esq."
        and args["cxxflags"] == "Robert Mc Roberts"
        and args["ldflags"] == '"-lpyodide_build_dir"'
        and args["replace_libs"] == "James Ignatius Morrison:Jimmy"
    )
