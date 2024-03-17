import shutil
import subprocess
import time
from pathlib import Path

import pydantic
import pytest

from pyodide_build import build_env, buildpkg, common
from pyodide_build.build_env import BuildArgs
from pyodide_build.buildpkg import RecipeBuilder
from pyodide_build.io import _SourceSpec

RECIPE_DIR = Path(__file__).parent / "_test_recipes"
WHEEL_DIR = Path(__file__).parent / "_test_wheels"


@pytest.fixture
def tmp_builder(tmp_path):
    # Dummy builder to test other functions
    builder = RecipeBuilder(
        recipe=RECIPE_DIR / "pkg_1",
        build_args=BuildArgs(),
        build_dir=tmp_path,
        force_rebuild=False,
        continue_=False,
    )

    yield builder


def test_constructor(tmp_path):
    builder = RecipeBuilder(
        recipe=RECIPE_DIR / "beautifulsoup4",
        build_args=BuildArgs(),
        build_dir=tmp_path / "beautifulsoup4" / "build",
        force_rebuild=False,
        continue_=False,
    )

    assert builder.name == "beautifulsoup4"
    assert builder.version == "4.10.0"
    assert builder.fullname == "beautifulsoup4-4.10.0"

    assert builder.pkg_root == RECIPE_DIR / "beautifulsoup4"
    assert builder.build_dir == tmp_path / "beautifulsoup4" / "build"
    assert (
        builder.src_extract_dir
        == tmp_path / "beautifulsoup4" / "build" / "beautifulsoup4-4.10.0"
    )
    assert (
        builder.src_dist_dir
        == tmp_path / "beautifulsoup4" / "build" / "beautifulsoup4-4.10.0" / "dist"
    )
    assert builder.dist_dir == RECIPE_DIR / "beautifulsoup4" / "dist"
    assert builder.library_install_prefix == tmp_path / ".libs"


def test_load_recipe(tmp_builder):
    root, recipe = tmp_builder._load_recipe(RECIPE_DIR / "pkg_1")
    assert root == RECIPE_DIR / "pkg_1"
    assert recipe.package.name == "pkg_1"

    root, recipe = tmp_builder._load_recipe(RECIPE_DIR / "pkg_1" / "meta.yaml")
    assert root == RECIPE_DIR / "pkg_1"
    assert recipe.package.name == "pkg_1"


def test_prepare_source(monkeypatch, tmp_path):
    class subprocess_result:
        returncode = 0
        stdout = ""

    build_env.get_build_environment_vars()
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess_result)
    monkeypatch.setattr(buildpkg, "check_checksum", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "unpack_archive", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "move", lambda *args, **kwargs: True)

    test_pkgs = [
        RECIPE_DIR / "packaging/meta.yaml",
        RECIPE_DIR / "micropip/meta.yaml",
    ]

    for pkg in test_pkgs:
        builder = RecipeBuilder(
            recipe=pkg,
            build_args=BuildArgs(),
            build_dir=tmp_path,
        )
        builder._prepare_source()
        assert builder.src_extract_dir.is_dir()


def test_check_executables(tmp_path, monkeypatch):
    builder = RecipeBuilder(
        recipe=RECIPE_DIR / "pkg_test_executable",
        build_args=BuildArgs(),
        build_dir=tmp_path,
    )

    monkeypatch.setattr(
        common, "find_missing_executables", lambda executables: ["echo"]
    )
    with pytest.raises(
        RuntimeError, match="The following executables are required to build"
    ):
        builder._check_executables()


def test_get_helper_vars(tmp_path):
    builder = RecipeBuilder(
        recipe=RECIPE_DIR / "pkg_1",
        build_args=BuildArgs(),
        build_dir=tmp_path / "pkg_1" / "build",
    )

    helper_vars = builder._get_helper_vars()

    assert helper_vars["PKGDIR"] == str(RECIPE_DIR / "pkg_1")
    assert helper_vars["PKG_VERSION"] == "1.0.0"
    assert helper_vars["PKG_BUILD_DIR"] == str(
        tmp_path / "pkg_1" / "build" / "pkg_1-1.0.0"
    )
    assert helper_vars["DISTDIR"] == str(
        tmp_path / "pkg_1" / "build" / "pkg_1-1.0.0" / "dist"
    )
    assert helper_vars["WASM_LIBRARY_DIR"] == str(tmp_path / ".libs")
    assert helper_vars["PKG_CONFIG_LIBDIR"] == str(
        tmp_path / ".libs" / "lib" / "pkgconfig"
    )


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

    n_moved = buildpkg.unvendor_tests(install_prefix, test_install_prefix, [])

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
    pkg_root = Path(tmpdir)
    buildpath = pkg_root / "build"
    meta_yaml = pkg_root / "meta.yaml"
    packaged = buildpath / ".packaged"

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

    buildpath.mkdir()
    meta_yaml.touch()
    patch_file.touch()
    extra_file.touch()
    src_path.mkdir()
    src_path_file.touch()

    # No .packaged file, rebuild
    assert buildpkg.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # .packaged file exists, no rebuild
    packaged.touch()
    assert buildpkg.needs_rebuild(pkg_root, buildpath, source_metadata) is False

    # newer meta.yaml file, rebuild
    packaged.touch()
    time.sleep(0.01)
    meta_yaml.touch()
    assert buildpkg.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # newer patch file, rebuild
    packaged.touch()
    time.sleep(0.01)
    patch_file.touch()
    assert buildpkg.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # newer extra file, rebuild
    packaged.touch()
    time.sleep(0.01)
    extra_file.touch()
    assert buildpkg.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # newer source path, rebuild
    packaged.touch()
    time.sleep(0.01)
    src_path_file.touch()
    assert buildpkg.needs_rebuild(pkg_root, buildpath, source_metadata) is True

    # newer .packaged file, no rebuild
    packaged.touch()
    assert buildpkg.needs_rebuild(pkg_root, buildpath, source_metadata) is False


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
