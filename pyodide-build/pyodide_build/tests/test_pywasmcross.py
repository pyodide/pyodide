import subprocess
from dataclasses import dataclass
from typing import Any

import pytest

from pyodide_build.pywasmcross import handle_command_generate_args  # noqa: E402
from pyodide_build.pywasmcross import replay_f2c  # noqa: E402
from pyodide_build.pywasmcross import (
    calculate_exports,
    environment_substitute_args,
    get_cmake_compiler_flags,
)


@dataclass
class BuildArgs:
    """An object to hold build arguments"""

    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
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

    if res[0] in ("emcc", "em++"):
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

    proxied_commands = {
        "cc": "emcc",
        "c++": "em++",
        "gcc": "emcc",
        "ld": "emcc",
        "ar": "emar",
        "ranlib": "emranlib",
        "strip": "emstrip",
        "cmake": "emcmake",
    }

    for cmd, proxied_cmd in proxied_commands.items():
        assert generate_args(cmd, args).split()[0] == proxied_cmd

    assert (
        generate_args("gcc -c test.o -o test.so", args, True)
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
        target_install_dir="",
    )
    assert (
        generate_args("gcc -c test.o -o test.so", args, True)
        == "emcc -lm -c test.o -o test.so"
    )

    # Test that repeated libraries are removed
    assert (
        generate_args("gcc test.o -lbob -ljim -ljim -lbob -o test.so", args)
        == "emcc test.o -lbob -ljim -o test.so"
    )


def test_handle_command_ldflags():
    # Make sure to remove unsupported link flags for wasm-ld

    args = BuildArgs()
    assert (
        generate_args(
            "gcc -Wl,--strip-all,--as-needed -Wl,--sort-common,-z,now,-Bsymbolic-functions -c test.o -o test.so",
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
    assert generate_args("gcc -c test.o -B /compiler_compat -o test.so", args) == (
        "emcc -c test.o -o test.so"
    )

    assert generate_args("gcc -c test.o -Wl,--sysroot=/ -o test.so", args) == (
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
        }
    )
    assert (
        args["cflags"] == "Frederick F. Freddertson Esq."
        and args["cxxflags"] == "Robert Mc Roberts"
        and args["ldflags"] == '"-lpyodide_build_dir"'
    )


@pytest.mark.xfail(reason="FIXME: emcc is not available during test")
def test_exports_node(tmp_path):
    template = """
        int l();

        __attribute__((visibility("hidden")))
        int f%s() {
            return l();
        }

        __attribute__ ((visibility ("default")))
        int g%s() {
            return l();
        }

        int h%s(){
            return l();
        }
        """
    (tmp_path / "f1.c").write_text(template % (1, 1, 1))
    (tmp_path / "f2.c").write_text(template % (2, 2, 2))
    subprocess.run(["emcc", "-c", tmp_path / "f1.c", "-o", tmp_path / "f1.o", "-fPIC"])
    subprocess.run(["emcc", "-c", tmp_path / "f2.c", "-o", tmp_path / "f2.o", "-fPIC"])
    assert set(calculate_exports([str(tmp_path / "f1.o")], True)) == {"g1", "h1"}
    assert set(
        calculate_exports([str(tmp_path / "f1.o"), str(tmp_path / "f2.o")], True)
    ) == {
        "g1",
        "h1",
        "g2",
        "h2",
    }
    # Currently if the object file contains bitcode we can't tell what the
    # symbol visibility is.
    subprocess.run(
        ["emcc", "-c", tmp_path / "f1.c", "-o", tmp_path / "f1.o", "-fPIC", "-flto"]
    )
    assert set(calculate_exports([str(tmp_path / "f1.o")], True)) == {"f1", "g1", "h1"}


def test_get_cmake_compiler_flags():
    cmake_flags = " ".join(get_cmake_compiler_flags())

    compiler_flags = (
        "CMAKE_C_COMPILER",
        "CMAKE_CXX_COMPILER",
        "CMAKE_C_COMPILER_AR",
        "CMAKE_CXX_COMPILER_AR",
    )

    for compiler_flag in compiler_flags:
        assert f"-D{compiler_flag}" in cmake_flags

    emscripten_compilers = (
        "emcc",
        "em++",
        "emar",
    )

    for emscripten_compiler in emscripten_compilers:
        assert emscripten_compiler not in cmake_flags
