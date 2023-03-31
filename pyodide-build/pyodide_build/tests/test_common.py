import zipfile

import pytest

from pyodide_build.common import (
    environment_substitute_args,
    find_matching_wheels,
    find_missing_executables,
    get_make_environment_vars,
    get_make_flag,
    get_num_cores,
    make_zip_archive,
    parse_top_level_import_name,
    platform,
    repack_zip_archive,
    search_pyodide_root,
)


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
        f"{current_version}-none-any",
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

    s = f"""\
emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) {common.emscripten_version()} (4343cbec72b7db283ea3bda1adc6cb1811ae9a73)
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


@pytest.mark.parametrize(
    "pkg",
    [
        {
            "name": "pkg_singlefile-1.0.0-py3-none-any.whl",
            "file": "singlefile.py",
            "content": "pass\n",
            "top_level": ["singlefile"],
        },
        {
            "name": "pkg_flit-1.0.0-py3-none-any.whl",
            "file": "pkg_flit/__init__.py",
            "content": "pass\n",
            "top_level": ["pkg_flit"],
        },
    ],
)
def test_parse_top_level_import_name(pkg, tmp_path):
    with zipfile.ZipFile(tmp_path / pkg["name"], "w") as whlzip:
        whlzip.writestr(pkg["file"], data=pkg["content"])

    top_level = parse_top_level_import_name(tmp_path / pkg["name"])
    assert top_level == pkg["top_level"]


def test_find_missing_executables(monkeypatch):
    import shutil

    pkgs = ["a", "b", "c"]
    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda exe: None)
        assert pkgs == find_missing_executables(pkgs)

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda exe: "/bin")
        assert [] == find_missing_executables(pkgs)


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


@pytest.mark.parametrize("num_cpus", [1, 2, 3])
def test_get_num_cores(monkeypatch, num_cpus):
    import loky

    with monkeypatch.context() as m:
        m.setattr(loky, "cpu_count", lambda: num_cpus)

        assert get_num_cores() == num_cpus


@pytest.mark.parametrize(
    "compression_level, expected_compression_type",
    [(6, zipfile.ZIP_DEFLATED), (0, zipfile.ZIP_STORED)],
)
def test_make_zip_archive(tmp_path, compression_level, expected_compression_type):
    input_dir = tmp_path / "a"
    input_dir.mkdir()
    (input_dir / "b.txt").write_text(".")
    (input_dir / "c").mkdir()
    (input_dir / "c/d").write_bytes(b"")

    output_dir = tmp_path / "output.zip"

    make_zip_archive(output_dir, input_dir, compression_level=compression_level)

    with zipfile.ZipFile(output_dir) as fh:
        assert set(fh.namelist()) == {"b.txt", "c/", "c/d"}
        assert fh.read("b.txt") == b"."
        assert fh.getinfo("b.txt").compress_type == expected_compression_type


@pytest.mark.parametrize(
    "compression_level, expected_compression_type, expected_size",
    [(6, zipfile.ZIP_DEFLATED, 220), (0, zipfile.ZIP_STORED, 1207)],
)
def test_repack_zip_archive(
    tmp_path, compression_level, expected_compression_type, expected_size
):
    input_path = tmp_path / "archive.zip"

    data = "a" * 1000

    with zipfile.ZipFile(
        input_path, "w", compression=zipfile.ZIP_BZIP2, compresslevel=3
    ) as fh:
        fh.writestr("a/b.txt", data)
        fh.writestr("a/b/c.txt", "d")

    repack_zip_archive(input_path, compression_level=compression_level)

    with zipfile.ZipFile(input_path) as fh:
        assert fh.namelist() == ["a/b.txt", "a/b/c.txt"]
        assert fh.getinfo("a/b.txt").compress_type == expected_compression_type
    assert input_path.stat().st_size == expected_size
