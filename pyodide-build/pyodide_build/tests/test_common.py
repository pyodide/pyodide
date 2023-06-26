import zipfile

import pytest

from pyodide_build.common import (
    environment_substitute_args,
    find_missing_executables,
    get_num_cores,
    make_zip_archive,
    parse_top_level_import_name,
    repack_zip_archive,
)


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
