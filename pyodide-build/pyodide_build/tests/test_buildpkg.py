import shutil
import subprocess
import time
from pathlib import Path

import pytest

from pyodide_build import buildpkg
from pyodide_build.io import parse_package_config


def test_subprocess_with_shared_env():
    p = buildpkg.BashRunnerWithSharedEnvironment()
    p.env.pop("A", None)

    res = p.run("A=6; echo $A", stdout=subprocess.PIPE)
    assert res.stdout == b"6\n"
    assert p.env.get("A", None) is None

    p.run("export A=2")
    assert p.env["A"] == "2"

    res = p.run("echo $A", stdout=subprocess.PIPE)
    assert res.stdout == b"2\n"

    res = p.run("A=6; echo $A", stdout=subprocess.PIPE)
    assert res.stdout == b"6\n"
    assert p.env.get("A", None) == "6"

    p.env["A"] = "7"
    res = p.run("echo $A", stdout=subprocess.PIPE)
    assert res.stdout == b"7\n"
    assert p.env["A"] == "7"


def test_prepare_source(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: True)
    monkeypatch.setattr(buildpkg, "check_checksum", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "unpack_archive", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "move", lambda *args, **kwargs: True)

    test_pkgs = []

    # tarballname == version
    test_pkgs.append(parse_package_config("./packages/scipy/meta.yaml"))
    test_pkgs.append(parse_package_config("./packages/numpy/meta.yaml"))

    # tarballname != version
    test_pkgs.append(
        {
            "package": {"name": "pyyaml", "version": "5.3.1"},
            "source": {
                "url": "https://files.pythonhosted.org/packages/64/c2/b80047c7ac2478f9501676c988a5411ed5572f35d1beff9cae07d321512c/PyYAML-5.3.1.tar.gz"
            },
        }
    )

    for pkg in test_pkgs:
        pkg["source"]["patches"] = []

    for pkg in test_pkgs:
        source_dir_name = pkg["package"]["name"] + "-" + pkg["package"]["version"]
        pkg_root = Path(pkg["package"]["name"])
        buildpath = pkg_root / "build"
        src_metadata = pkg["source"]
        srcpath = buildpath / source_dir_name
        buildpkg.prepare_source(pkg_root, buildpath, srcpath, src_metadata)


@pytest.mark.parametrize("is_library", [True, False])
def test_run_script(is_library, tmpdir):
    build_dir = Path(tmpdir.mkdir("build"))
    src_dir = Path(tmpdir.mkdir("build/package_name"))
    script = "touch out.txt"
    build_metadata = {"script": script, "library": is_library}
    shared_env = buildpkg.BashRunnerWithSharedEnvironment()
    buildpkg.run_script(build_dir, src_dir, build_metadata, shared_env)
    assert (src_dir / "out.txt").exists()


def test_run_script_environment(tmpdir):
    build_dir = Path(tmpdir.mkdir("build"))
    src_dir = Path(tmpdir.mkdir("build/package_name"))
    script = "export A=2"
    build_metadata = {"script": script, "library": False}
    shared_env = buildpkg.BashRunnerWithSharedEnvironment()
    shared_env.env.pop("A", None)
    buildpkg.run_script(build_dir, src_dir, build_metadata, shared_env)
    assert shared_env.env["A"] == "2"


def test_unvendor_tests(tmpdir):
    def touch(path: Path):
        if path.is_dir():
            raise ValueError("Only files, not folders are supported")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    def rlist(input_dir):
        """Recursively list files in input_dir"""
        paths = list(sorted(input_dir.rglob("*")))
        res = []

        for el in paths:
            if el.is_file():
                res.append(str(el.relative_to(input_dir)))
        return res

    install_prefix = Path(str(tmpdir / "install"))
    test_install_prefix = Path(str(tmpdir / "install-tests"))

    # create the example package
    touch(install_prefix / "ex1" / "base.py")
    touch(install_prefix / "ex1" / "conftest.py")
    touch(install_prefix / "ex1" / "test_base.py")
    touch(install_prefix / "ex1" / "tests" / "data.csv")
    touch(install_prefix / "ex1" / "tests" / "test_a.py")

    n_moved = buildpkg.unvendor_tests(install_prefix, test_install_prefix)

    assert rlist(install_prefix) == ["ex1/base.py"]
    assert rlist(test_install_prefix) == [
        "ex1/conftest.py",
        "ex1/test_base.py",
        "ex1/tests/data.csv",
        "ex1/tests/test_a.py",
    ]

    # One test folder and two test file
    assert n_moved == 3


def test_needs_rebuild(tmpdir):
    pkg_root = tmpdir
    pkg_root = Path(pkg_root)
    builddir = pkg_root / "build"
    meta_yaml = pkg_root / "meta.yaml"
    packaged = builddir / ".packaged"

    patch_file = pkg_root / "patch"
    extra_file = pkg_root / "extra"
    src_path = pkg_root / "src"
    src_path_file = src_path / "file"
    source_metadata = {
        "patches": [
            str(patch_file),
        ],
        "extras": [
            (str(extra_file), ""),
        ],
        "path": str(src_path),
    }

    builddir.mkdir()
    meta_yaml.touch()
    patch_file.touch()
    extra_file.touch()
    src_path.mkdir()
    src_path_file.touch()

    # No .packaged file, rebuild
    assert buildpkg.needs_rebuild(pkg_root, builddir, source_metadata) is True

    # .packaged file exists, no rebuild
    packaged.touch()
    assert buildpkg.needs_rebuild(pkg_root, builddir, source_metadata) is False

    # newer meta.yaml file, rebuild
    packaged.touch()
    time.sleep(0.01)
    meta_yaml.touch()
    assert buildpkg.needs_rebuild(pkg_root, builddir, source_metadata) is True

    # newer patch file, rebuild
    packaged.touch()
    time.sleep(0.01)
    patch_file.touch()
    assert buildpkg.needs_rebuild(pkg_root, builddir, source_metadata) is True

    # newer extra file, rebuild
    packaged.touch()
    time.sleep(0.01)
    extra_file.touch()
    assert buildpkg.needs_rebuild(pkg_root, builddir, source_metadata) is True

    # newer source path, rebuild
    packaged.touch()
    time.sleep(0.01)
    src_path_file.touch()
    assert buildpkg.needs_rebuild(pkg_root, builddir, source_metadata) is True

    # newer .packaged file, no rebuild
    packaged.touch()
    assert buildpkg.needs_rebuild(pkg_root, builddir, source_metadata) is False
