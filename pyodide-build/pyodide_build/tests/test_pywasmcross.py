import subprocess

import pytest

from pyodide_build.pywasmcross import (
    CrossCompileArgs,
    calculate_exports,
    filter_objects,
    get_cmake_compiler_flags,
    handle_command_generate_args,
    is_link_cmd,
    replay_genargs_handle_dashI,
)


@pytest.fixture(scope="function")
def build_args():
    yield CrossCompileArgs(
        cflags="",
        cxxflags="",
        ldflags="",
        target_install_dir="",
        pythoninclude="python/include",
        exports="whole_archive",
    )


def generate_args(line: str, args: CrossCompileArgs, is_link_cmd: bool = False) -> str:
    splitline = line.split()
    res = handle_command_generate_args(splitline, args)

    if res[0] in ("emcc", "em++"):
        for arg in [
            "-Werror=implicit-function-declaration",
            "-Werror=mismatched-parameter-types",
            "-Werror=return-type",
        ]:
            assert arg in res
            res.remove(arg)

    if "-c" in splitline:
        if "python/include" in res:
            include_index = res.index("python/include")
            del res[include_index]
            del res[include_index - 1]

    if is_link_cmd:
        arg = "-Wl,--fatal-warnings"
        assert arg in res
        res.remove(arg)
    return " ".join(res)


def test_handle_command(build_args):
    args = build_args
    assert handle_command_generate_args(["gcc", "-print-multiarch"], args) == [
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
    args = CrossCompileArgs(
        cflags="-I./lib2",
        cxxflags="-std=c++11",
        ldflags="-lm",
        exports="whole_archive",
    )
    assert (
        generate_args("gcc -I./lib1 -c test.cpp -o test.o", args)
        == "em++ -I./lib1 -c test.cpp -o test.o -I./lib2 -std=c++11"
    )

    # check ldflags injection
    args = CrossCompileArgs(
        cflags="",
        cxxflags="",
        ldflags="-lm",
        target_install_dir="",
        exports="whole_archive",
    )
    assert (
        generate_args("gcc -c test.o -o test.so", args, True)
        == "emcc -c test.o -o test.so -lm"
    )

    # Test that repeated libraries are removed
    assert (
        generate_args("gcc test.o -lbob -ljim -ljim -lbob -o test.so", args, True)
        == "emcc test.o -lbob -ljim -o test.so -lm"
    )


def test_handle_command_ldflags(build_args):
    # Make sure to remove unsupported link flags for wasm-ld

    args = build_args
    assert (
        generate_args(
            "gcc -Wl,--strip-all,--as-needed -Wl,--sort-common,-z,now,-Bsymbolic-functions -c test.o -o test.so",
            args,
            True,
        )
        == "emcc -Wl,-z,now -c test.o -o test.so"
    )


def test_replay_genargs_handle_dashI(monkeypatch):
    import sys

    mock_prefix = "/mock_prefix"
    mock_base_prefix = "/mock_base_prefix"
    monkeypatch.setattr(sys, "prefix", mock_prefix)
    monkeypatch.setattr(sys, "base_prefix", mock_base_prefix)

    target_dir = "/target"
    target_cpython_include = "/target/include/python3.11"

    assert replay_genargs_handle_dashI("-I/usr/include", target_dir) is None
    assert (
        replay_genargs_handle_dashI(f"-I{mock_prefix}/include/python3.11", target_dir)
        == f"-I{target_cpython_include}"
    )
    assert (
        replay_genargs_handle_dashI(
            f"-I{mock_base_prefix}/include/python3.11", target_dir
        )
        == f"-I{target_cpython_include}"
    )


def test_conda_unsupported_args(build_args):
    # Check that compile arguments that are not supported by emcc and are sometimes
    # used in conda are removed.
    args = build_args
    assert generate_args(
        "gcc -c test.o -B /compiler_compat -o test.so", args, True
    ) == ("emcc -c test.o -o test.so")

    assert generate_args("gcc -c test.o -Wl,--sysroot=/ -o test.so", args, True) == (
        "emcc -c test.o -o test.so"
    )


@pytest.mark.parametrize(
    "line, expected",
    [
        ([], []),
        (
            [
                "obj1.o",
                "obj2.o",
                "slib1.so",
                "slib2.so",
                "lib1.a",
                "lib2.a",
                "-o",
                "test.so",
            ],
            ["obj1.o", "obj2.o", "lib1.a", "lib2.a"],
        ),
        (
            ["@dir/link.txt", "obj1.o", "obj2.o", "test.so"],
            ["@dir/link.txt", "obj1.o", "obj2.o"],
        ),
    ],
)
def test_filter_objects(line, expected):
    assert filter_objects(line) == expected


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


def test_handle_command_cmake(build_args):
    args = build_args
    assert "--fresh" in handle_command_generate_args(["cmake", "./"], args)

    build_cmd = ["cmake", "--build", "." "--target", "target"]
    assert handle_command_generate_args(build_cmd, args) == build_cmd


def test_is_link_cmd():
    assert is_link_cmd(["test.so"])
    assert is_link_cmd(["test.so.1.2.3"])
    assert not is_link_cmd(["test", "test.a", "test.o", "test.c", "test.cpp", "test.h"])
