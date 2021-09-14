import shutil
import subprocess

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


def test_download_and_extract(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: True)
    monkeypatch.setattr(buildpkg, "check_checksum", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "unpack_archive", lambda *args, **kwargs: True)

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
        packagedir = pkg["package"]["name"] + "-" + pkg["package"]["version"]
        buildpath = Path(pkg["package"]["name"]) / "build"
        srcpath = buildpkg.download_and_extract(buildpath, packagedir, pkg, args=None)

        assert srcpath.name.lower().endswith(packagedir.lower())


@pytest.mark.parametrize("is_library", [True, False])
def test_run_script(is_library, tmpdir):
    build_dir = Path(tmpdir.mkdir("build"))
    src_dir = Path(tmpdir.mkdir("build/package_name"))
    script = "touch out.txt"
    pkg = {"build": {"script": script, "library": is_library}}
    shared_env = buildpkg.BashRunnerWithSharedEnvironment()
    buildpkg.run_script(build_dir, src_dir, pkg, shared_env)
    assert (src_dir / "out.txt").exists()
    if is_library:
        assert (build_dir / ".packaged").exists()
    else:
        assert not (build_dir / ".packaged").exists()


def test_run_script_environment(tmpdir):
    build_dir = Path(tmpdir.mkdir("build"))
    src_dir = Path(tmpdir.mkdir("build/package_name"))
    script = "export A=2"
    pkg = {"build": {"script": script, "library": False}}
    shared_env = buildpkg.BashRunnerWithSharedEnvironment()
    shared_env.env.pop("A", None)
    buildpkg.run_script(build_dir, src_dir, pkg, shared_env)
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
