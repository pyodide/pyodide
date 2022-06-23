from dataclasses import dataclass
from typing import Any

import pytest

from pyodide_build.pywasmcross import handle_command_generate_args  # noqa: E402
from pyodide_build.pywasmcross import replay_f2c  # noqa: E402
from pyodide_build.pywasmcross import environment_substitute_args


@dataclass
class BuildArgs:
    """An object to hold build arguments"""

    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    replace_libs: str = ""
    target_install_dir: str = ""
    pythoninclude: str = "python/include"
    exports: str = "whole_archive"


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


def generate_args(line: str, args: Any, is_link_cmd: bool = False) -> str:
    splitline = line.split()
    res = handle_command_generate_args(splitline, args, is_link_cmd)
    for arg in [
        "-Werror=implicit-function-declaration",
        "-Werror=mismatched-parameter-types",
        "-Werror=return-type",
    ]:
        assert arg in res
        res.remove(arg)
    if "-c" in splitline:
        include_index = res.index("python/include")
        del res[include_index]
        del res[include_index - 1]

    if is_link_cmd:
        arg = "-Wl,--fatal-warnings"
        assert arg in res
        res.remove(arg)
    return " ".join(res)


def test_handle_command():
    args = BuildArgs()
    assert handle_command_generate_args(["gcc", "-print-multiarch"], args, True) == [  # type: ignore[arg-type]
        "echo",
        "wasm32-emscripten",
    ]
    assert generate_args("gcc test.c", args) == "emcc test.c"
    assert (
        generate_args("gcc -shared -c test.o -o test.so", args, True)
        == "emcc -c test.o -o test.so"
    )

    # check cxxflags injection and cpp detection
    args = BuildArgs(
        cflags="-I./lib2",
        cxxflags="-std=c++11",
        ldflags="-lm",
    )
    assert (
        generate_args("gcc -I./lib1 -c test.cpp -o test.o", args)
        == "em++ -I./lib2 -std=c++11 -I./lib1 -c test.cpp -o test.o"
    )

    # check ldflags injection
    args = BuildArgs(
        cflags="",
        cxxflags="",
        ldflags="-lm",
        replace_libs="",
        target_install_dir="",
    )
    assert (
        generate_args("gcc -shared -c test.o -o test.so", args, True)
        == "emcc -lm -c test.o -o test.so"
    )

    # check library replacement and removal of double libraries
    args = BuildArgs(
        replace_libs="bob=fred",
    )
    assert (
        generate_args("gcc -shared test.o -lbob -ljim -ljim -o test.so", args)
        == "emcc test.o -lfred -ljim -o test.so"
    )


def test_handle_command_ldflags():
    # Make sure to remove unsupported link flags for wasm-ld

    args = BuildArgs()
    assert (
        generate_args(
            "gcc -Wl,--strip-all,--as-needed -Wl,--sort-common,-z,now,-Bsymbolic-functions -shared -c test.o -o test.so",
            args,
            True,
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
        generate_args(f"gcc -O3 -c test.{in_ext} -o test.{out_ext}", args, True)
        == f"{executable} -Oz -c test.{in_ext} -o test.{out_ext}"
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
    # Check that compile arguments that are not supported by emcc and are sometimes
    # used in conda are removed.
    args = BuildArgs()
    assert generate_args(
        "gcc -shared -c test.o -B /compiler_compat -o test.so", args
    ) == ("emcc -c test.o -o test.so")

    assert generate_args("gcc -shared -c test.o -Wl,--sysroot=/ -o test.so", args) == (
        "emcc -c test.o -o test.so"
    )


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
