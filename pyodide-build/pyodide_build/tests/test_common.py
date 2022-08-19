import pytest

from pyodide_build.common import (
    ALWAYS_PACKAGES,
    CORE_PACKAGES,
    CORE_SCIPY_PACKAGES,
    _parse_package_subset,
    find_matching_wheels,
    get_make_environment_vars,
    get_make_flag,
    platform,
    search_pyodide_root,
)


def test_parse_package_subset():
    assert (
        _parse_package_subset("numpy,pandas")
        == {
            "numpy",
            "pandas",
        }
        | ALWAYS_PACKAGES
    )

    # duplicates are removed
    assert (
        _parse_package_subset("numpy,numpy")
        == {
            "numpy",
        }
        | ALWAYS_PACKAGES
    )

    # no empty package name included, spaces are handled
    assert (
        _parse_package_subset("x,  a, b, c   ,,, d,,")
        == {
            "x",
            "a",
            "b",
            "c",
            "d",
        }
        | ALWAYS_PACKAGES
    )

    assert _parse_package_subset("core") == CORE_PACKAGES | ALWAYS_PACKAGES
    # by default core packages are built
    assert _parse_package_subset(None) == _parse_package_subset("core")

    assert (
        _parse_package_subset("min-scipy-stack")
        == CORE_SCIPY_PACKAGES | CORE_PACKAGES | ALWAYS_PACKAGES
    )
    # reserved key words can be combined with other packages
    assert _parse_package_subset("core, unknown") == _parse_package_subset("core") | {
        "unknown"
    }


def test_get_make_flag():
    assert len(get_make_flag("SIDE_MODULE_LDFLAGS")) > 0
    assert len(get_make_flag("SIDE_MODULE_CFLAGS")) > 0
    # n.b. right now CXXFLAGS is empty so don't check length here, just check it returns
    get_make_flag("SIDE_MODULE_CXXFLAGS")


def test_get_make_environment_vars():
    vars = get_make_environment_vars()
    assert "SIDE_MODULE_LDFLAGS" in vars
    assert "SIDE_MODULE_CFLAGS" in vars
    assert "SIDE_MODULE_CXXFLAGS" in vars
    assert "TOOLSDIR" in vars


def test_wheel_paths():
    from pathlib import Path

    old_version = "cp38"
    PYMAJOR = int(get_make_flag("PYMAJOR"))
    PYMINOR = int(get_make_flag("PYMINOR"))
    PLATFORM = platform()
    current_version = f"cp{PYMAJOR}{PYMINOR}"
    future_version = f"cp{PYMAJOR}{PYMINOR + 1}"
    strings = []

    for interp in [
        old_version,
        current_version,
        future_version,
        "py3",
        "py2",
        "py2.py3",
    ]:
        for abi in [interp, "abi3", "none"]:
            for arch in [PLATFORM, "linux_x86_64", "any"]:
                strings.append(f"wrapt-1.13.3-{interp}-{abi}-{arch}.whl")

    paths = [Path(x) for x in strings]
    assert [x.stem.split("-", 2)[-1] for x in find_matching_wheels(paths)] == [
        f"{current_version}-{current_version}-{PLATFORM}",
        f"{current_version}-abi3-{PLATFORM}",
        f"{current_version}-none-{PLATFORM}",
        f"{old_version}-abi3-{PLATFORM}",
        f"py3-none-{PLATFORM}",
        f"py2.py3-none-{PLATFORM}",
        "py3-none-any",
        "py2.py3-none-any",
    ]


def test_search_pyodide_root(tmp_path):
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("[tool.pyodide]")
    assert search_pyodide_root(tmp_path) == tmp_path
    assert search_pyodide_root(tmp_path / "subdir") == tmp_path
    assert search_pyodide_root(tmp_path / "subdir" / "subdir") == tmp_path

    pyproject_file.unlink()
    with pytest.raises(FileNotFoundError):
        search_pyodide_root(tmp_path)


def test_check_emscripten_version(monkeypatch):
    from pyodide_build import common

    s = None

    def get_emscripten_version_info():
        return s

    needed_version = common.emscripten_version()
    monkeypatch.setattr(
        common, "get_emscripten_version_info", get_emscripten_version_info
    )
    s = """\
emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 3.1.4 (14cd48e6ead13b02a79f47df1a252abc501a3269)
clang version 15.0.0 (https://github.com/llvm/llvm-project ce5588fdf478b6af724977c11a405685cebc3d26)
Target: wasm32-unknown-emscripten
Thread model: posix
"""
    with pytest.raises(
        RuntimeError,
        match=f"Incorrect Emscripten version 3.1.4. Need Emscripten version {needed_version}",
    ):
        common.check_emscripten_version()

    s = """\
emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 1.39.20
clang version 12.0.0 (/b/s/w/ir/cache/git/chromium.googlesource.com-external-github.com-llvm-llvm--project 55fa315b0352b63454206600d6803fafacb42d5e)
"""

    with pytest.raises(
        RuntimeError,
        match=f"Incorrect Emscripten version 1.39.20. Need Emscripten version {needed_version}",
    ):
        common.check_emscripten_version()

    s = """\
emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 3.1.14 (4343cbec72b7db283ea3bda1adc6cb1811ae9a73)
clang version 15.0.0 (https://github.com/llvm/llvm-project 7effcbda49ba32991b8955821b8fdbd4f8f303e2)
"""
    common.check_emscripten_version()

    def get_emscripten_version_info():  # type: ignore[no-redef]
        raise FileNotFoundError()

    monkeypatch.setattr(
        common, "get_emscripten_version_info", get_emscripten_version_info
    )

    with pytest.raises(
        RuntimeError,
        match=f"No Emscripten compiler found. Need Emscripten version {needed_version}",
    ):
        common.check_emscripten_version()
