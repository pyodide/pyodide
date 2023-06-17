import shutil
import subprocess
import time
from pathlib import Path

import pydantic

from pyodide_build import buildpkg, common
from pyodide_build.io import MetaConfig, _SourceSpec

RECIPE_DIR = Path(__file__).parent / "_test_recipes"
WHEEL_DIR = Path(__file__).parent / "_test_wheels"


def test_subprocess_with_shared_env_1():
    with buildpkg.BashRunnerWithSharedEnvironment() as p:
        p.env.pop("A", None)

        res = p.run_unchecked("A=6; echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "6\n"
        assert p.env.get("A", None) is None

        p.run_unchecked("export A=2")
        assert p.env["A"] == "2"

        res = p.run_unchecked("echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "2\n"

        res = p.run_unchecked("A=6; echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "6\n"
        assert p.env.get("A", None) == "6"

        p.env["A"] = "7"
        res = p.run_unchecked("echo $A", stdout=subprocess.PIPE)
        assert res.stdout == "7\n"
        assert p.env["A"] == "7"


def test_subprocess_with_shared_env_cwd(tmp_path: Path) -> None:
    src_dir = tmp_path / "build/package_name"
    src_dir.mkdir(parents=True)
    script = "touch out.txt"
    with buildpkg.BashRunnerWithSharedEnvironment() as shared_env:
        shared_env.run_unchecked(script, cwd=src_dir)
        assert (src_dir / "out.txt").exists()


def test_subprocess_with_shared_env_logging(capfd, tmp_path):
    from pytest import raises

    with buildpkg.BashRunnerWithSharedEnvironment() as p:
        p.run("echo 1000", script_name="a test script")
        cap = capfd.readouterr()
        assert [l.strip() for l in cap.out.splitlines()] == [
            f"Running a test script in {Path.cwd()}",
            "1000",
        ]
        assert cap.err == ""

        dir = tmp_path / "a"
        dir.mkdir()
        p.run("echo 1000", script_name="test script", cwd=dir)
        cap = capfd.readouterr()
        assert [l.strip() for l in cap.out.splitlines()] == [
            "Running test script in",
            str(dir),
            "1000",
        ]
        assert cap.err == ""

        dir = tmp_path / "b"
        dir.mkdir()
        with raises(SystemExit) as e:
            p.run("exit 7", script_name="test2 script", cwd=dir)
        cap = capfd.readouterr()
        assert e.value.args[0] == 7
        assert [l.strip() for l in cap.out.splitlines()] == [
            "Running test2 script in",
            str(dir),
        ]
        assert [l.strip() for l in cap.err.splitlines()] == [
            "ERROR: test2 script failed",
            "exit 7",
        ]


def test_prepare_source(monkeypatch):
    class subprocess_result:
        returncode = 0
        stdout = ""

    common.get_build_environment_vars()
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess_result)
    monkeypatch.setattr(buildpkg, "check_checksum", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "unpack_archive", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "move", lambda *args, **kwargs: True)

    test_pkgs = []

    test_pkgs.append(MetaConfig.from_yaml(RECIPE_DIR / "packaging/meta.yaml"))
    test_pkgs.append(MetaConfig.from_yaml(RECIPE_DIR / "micropip/meta.yaml"))

    for pkg in test_pkgs:
        pkg.source.patches = []

    for pkg in test_pkgs:
        source_dir_name = pkg.package.name + "-" + pkg.package.version
        pkg_root = Path(pkg.package.name)
        buildpath = pkg_root / "build"
        src_metadata = pkg.source
        srcpath = buildpath / source_dir_name
        buildpkg.prepare_source(buildpath, srcpath, src_metadata)

        assert srcpath.is_dir()


def test_unvendor_tests(tmpdir):
    def touch(path: Path) -> None:
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

    class MockSourceSpec(_SourceSpec):
        @pydantic.root_validator
        def _check_patches_extra(cls, values):
            return values

    source_metadata = MockSourceSpec(
        patches=[
            str(patch_file),
        ],
        extras=[
            (str(extra_file), ""),
        ],
        path=str(src_path),
    )

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


def test_copy_sharedlib(tmp_path):
    wheel_file_name = "sharedlib_test_py-1.0-cp310-cp310-emscripten_3_1_21_wasm32.whl"
    wheel = WHEEL_DIR / "wheel" / wheel_file_name
    libdir = WHEEL_DIR / "lib"

    wheel_copy = tmp_path / wheel_file_name
    shutil.copy(wheel, wheel_copy)

    common.unpack_wheel(wheel_copy)
    name, ver, _ = wheel.name.split("-", 2)
    wheel_dir_name = f"{name}-{ver}"
    wheel_dir = tmp_path / wheel_dir_name

    dep_map = buildpkg.copy_sharedlibs(wheel_copy, wheel_dir, libdir)

    deps = ("sharedlib-test.so", "sharedlib-test-dep.so", "sharedlib-test-dep2.so")
    for dep in deps:
        assert dep in dep_map
