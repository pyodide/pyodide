# flake8: noqa

import os
import shutil
from pathlib import Path

import pytest
from pytest_pyodide import spawn_web_server
import zipfile
import typer
from typer.testing import CliRunner  # type: ignore[import]
from typing import Any
from pyodide_build import common
from pyodide_build.cli import (
    build,
    build_recipes,
    config,
    create_zipfile,
    skeleton,
    xbuildenv,
    py_compile,
)

from .fixture import temp_python_lib, temp_python_lib2, temp_xbuildenv

only_node = pytest.mark.xfail_browsers(
    chrome="node only", firefox="node only", safari="node only"
)


runner = CliRunner()


def test_skeleton_pypi(tmp_path):
    test_pkg = "pytest-pyodide"
    old_version = "0.21.0"
    new_version = "0.22.0"

    result = runner.invoke(
        skeleton.app,
        [
            "pypi",
            test_pkg,
            "--recipe-dir",
            str(tmp_path),
            "--version",
            old_version,
        ],
    )
    assert result.exit_code == 0
    assert "pytest-pyodide/meta.yaml" in result.stdout

    result = runner.invoke(
        skeleton.app,
        [
            "pypi",
            test_pkg,
            "--recipe-dir",
            str(tmp_path),
            "--version",
            new_version,
            "--update",
        ],
    )
    assert result.exit_code == 0
    assert f"Updated {test_pkg} from {old_version} to {new_version}" in result.stdout

    result = runner.invoke(
        skeleton.app, ["pypi", test_pkg, "--recipe-dir", str(tmp_path)]
    )
    assert result.exit_code != 0
    assert "already exists" in str(result.exception)


def test_build_recipe(selenium, tmp_path):
    # TODO: Run this test without building Pyodide

    output_dir = tmp_path / "dist"
    recipe_dir = Path(__file__).parent / "_test_recipes"

    pkgs = {
        "pkg_test_tag_always": {},
        "pkg_test_graph1": {"pkg_test_graph2"},
        "pkg_test_graph3": {},
    }

    pkgs_to_build = pkgs.keys() | {p for v in pkgs.values() for p in v}

    for build_dir in recipe_dir.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.recipe)

    result = runner.invoke(
        app,
        [
            *pkgs.keys(),
            "--recipe-dir",
            recipe_dir,
            "--install",
            "--install-dir",
            output_dir,
        ],
    )

    assert result.exit_code == 0, result.stdout

    for pkg in pkgs_to_build:
        assert f"built {pkg} in" in result.stdout

    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == len(pkgs_to_build)


def test_build_recipe_no_deps(selenium, tmp_path):
    # TODO: Run this test without building Pyodide

    recipe_dir = Path(__file__).parent / "_test_recipes"

    for build_dir in recipe_dir.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.recipe)

    pkgs_to_build = ["pkg_test_graph1", "pkg_test_graph3"]
    result = runner.invoke(
        app,
        [
            *pkgs_to_build,
            "--recipe-dir",
            recipe_dir,
            "--no-deps",
        ],
    )

    assert result.exit_code == 0, result.stdout

    for pkg in pkgs_to_build:
        assert f"Succeeded building package {pkg}" in result.stdout

    for pkg in pkgs_to_build:
        dist_dir = recipe_dir / pkg / "dist"
        assert len(list(dist_dir.glob("*.whl"))) == 1


def test_build_recipe_no_deps_force_rebuild(selenium, tmp_path):
    # TODO: Run this test without building Pyodide

    recipe_dir = Path(__file__).parent / "_test_recipes"

    for build_dir in recipe_dir.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.recipe)

    pkg = "pkg_test_graph1"
    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            recipe_dir,
            "--no-deps",
        ],
    )

    assert result.exit_code == 0, result.stdout

    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            recipe_dir,
            "--no-deps",
        ],
    )

    assert result.exit_code == 0
    assert "Creating virtualenv isolated environment" not in result.stdout
    assert f"Succeeded building package {pkg}" in result.stdout

    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            recipe_dir,
            "--no-deps",
            "--force-rebuild",
        ],
    )

    assert result.exit_code == 0
    assert "Creating virtualenv isolated environment" in result.stdout
    assert f"Succeeded building package {pkg}" in result.stdout


def test_build_recipe_no_deps_continue(selenium, tmp_path):
    # TODO: Run this test without building Pyodide

    recipe_dir = Path(__file__).parent / "_test_recipes"

    for build_dir in recipe_dir.rglob("build"):
        shutil.rmtree(build_dir)

    app = typer.Typer()
    app.command()(build_recipes.recipe)

    pkg = "pkg_test_graph1"
    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            recipe_dir,
            "--no-deps",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert f"Succeeded building package {pkg}" in result.stdout

    for wheels in (recipe_dir / pkg / "build").rglob("*.whl"):
        wheels.unlink()

    pyproject_toml = next((recipe_dir / pkg / "build").rglob("pyproject.toml"))

    # Modify some metadata and check it is applied when rebuilt with --continue flag
    version = "99.99.99"
    with open(pyproject_toml, encoding="utf-8") as f:
        pyproject_data = f.read()

    pyproject_data = pyproject_data.replace(
        'version = "1.0.0"', f'version = "{version}"'
    )

    with open(pyproject_toml, "w", encoding="utf-8") as f:
        f.write(pyproject_data)

    result = runner.invoke(
        app,
        [
            pkg,
            "--recipe-dir",
            recipe_dir,
            "--no-deps",
            "--continue",
        ],
    )

    assert result.exit_code == 0
    assert f"Succeeded building package {pkg}" in result.stdout
    assert f"{pkg}-{version}-py3-none-any.whl" in result.stdout


def test_config_list():
    result = runner.invoke(
        config.app,
        [
            "list",
        ],
    )

    envs = result.stdout.splitlines()
    keys = [env.split("=")[0] for env in envs]

    for cfg_name in config.PYODIDE_CONFIGS.keys():
        assert cfg_name in keys


@pytest.mark.parametrize("cfg_name,env_var", config.PYODIDE_CONFIGS.items())
def test_config_get(cfg_name, env_var):
    result = runner.invoke(
        config.app,
        [
            "get",
            cfg_name,
        ],
    )

    assert result.stdout.strip() == common.get_build_flag(env_var)


def test_create_zipfile(temp_python_lib, temp_python_lib2, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    app = typer.Typer()
    app.command()(create_zipfile.main)

    result = runner.invoke(
        app,
        [
            str(temp_python_lib),
            str(temp_python_lib2),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Zip file created" in result.stdout
    assert output.exists()

    with ZipFile(output) as zf:
        assert "module1.py" in zf.namelist()
        assert "module2.py" in zf.namelist()
        assert "module3.py" in zf.namelist()
        assert "module4.py" in zf.namelist()


def test_create_zipfile_compile(temp_python_lib, temp_python_lib2, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    app = typer.Typer()
    app.command()(create_zipfile.main)

    result = runner.invoke(
        app,
        [
            str(temp_python_lib),
            str(temp_python_lib2),
            "--output",
            str(output),
            "--pycompile",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Zip file created" in result.stdout
    assert output.exists()

    with ZipFile(output) as zf:
        assert "module1.pyc" in zf.namelist()
        assert "module2.pyc" in zf.namelist()
        assert "module3.pyc" in zf.namelist()
        assert "module4.pyc" in zf.namelist()


def test_xbuildenv_create(selenium, tmp_path):
    # selenium fixture is added to ensure that Pyodide is built... it's a hack
    from conftest import package_is_built

    envpath = Path(tmp_path) / ".xbuildenv"
    result = runner.invoke(
        xbuildenv.app,
        [
            "create",
            str(envpath),
            "--skip-missing-files",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "xbuildenv created at" in result.stdout
    assert (envpath / "xbuildenv").exists()
    assert (envpath / "xbuildenv" / "pyodide-root").is_dir()
    assert (envpath / "xbuildenv" / "site-packages-extras").is_dir()
    assert (envpath / "xbuildenv" / "requirements.txt").exists()

    if not package_is_built("scipy"):
        # creating xbuildenv without building scipy will raise error
        result = runner.invoke(
            xbuildenv.app,
            [
                "create",
                str(tmp_path / ".xbuildenv"),
            ],
        )
        assert result.exit_code != 0, result.stdout
        assert isinstance(result.exception, FileNotFoundError), result.exception


def test_xbuildenv_install(tmp_path, temp_xbuildenv):
    envpath = Path(tmp_path) / ".xbuildenv"

    xbuildenv_url_base, xbuildenv_filename = temp_xbuildenv

    with spawn_web_server(xbuildenv_url_base) as (hostname, port, _):
        xbuildenv_url = f"http://{hostname}:{port}/{xbuildenv_filename}"
        result = runner.invoke(
            xbuildenv.app,
            [
                "install",
                "--path",
                str(envpath),
                "--download",
                "--url",
                xbuildenv_url,
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert "Downloading xbuild environment" in result.stdout, result.stdout
    assert "Installing xbuild environment" in result.stdout, result.stdout
    assert (envpath / "xbuildenv" / "pyodide-root").is_dir()
    assert (envpath / "xbuildenv" / "site-packages-extras").is_dir()
    assert (envpath / "xbuildenv" / "requirements.txt").exists()


@pytest.mark.parametrize("target", ["dir", "file"])
@pytest.mark.parametrize("compression_level", [0, 6])
def test_py_compile(tmp_path, target, compression_level):
    wheel_path = tmp_path / "python.zip"
    with zipfile.ZipFile(wheel_path, "w", compresslevel=3) as zf:
        zf.writestr("a1.py", "def f():\n    pass")

    if target == "dir":
        target_path = tmp_path
    elif target == "file":
        target_path = wheel_path

    py_compile.main(
        path=target_path, silent=False, keep=False, compression_level=compression_level
    )
    with zipfile.ZipFile(tmp_path / "python.zip", "r") as fh:
        if compression_level > 0:
            assert fh.filelist[0].compress_type == zipfile.ZIP_DEFLATED
        else:
            assert fh.filelist[0].compress_type == zipfile.ZIP_STORED


def test_build1(tmp_path, monkeypatch):
    from pyodide_build import pypabuild

    def mocked_build(srcdir: Path, outdir: Path, env: Any, backend_flags: Any) -> str:
        results["srcdir"] = srcdir
        results["outdir"] = outdir
        results["backend_flags"] = backend_flags
        return str(outdir / "a.whl")

    monkeypatch.setattr(common, "check_emscripten_version", lambda: None)
    monkeypatch.setattr(pypabuild, "build", mocked_build)

    results: dict[str, Any] = {}
    srcdir = tmp_path / "in"
    outdir = tmp_path / "out"
    srcdir.mkdir()
    app = typer.Typer()
    app.command(**build.main.typer_kwargs)(build.main)  # type:ignore[attr-defined]
    result = runner.invoke(app, [str(srcdir), "--outdir", str(outdir), "x", "y", "z"])
    print(result)
    print(result.stdout)
    assert result.exit_code == 0
    assert results["srcdir"] == srcdir
    assert results["outdir"] == outdir
    assert results["backend_flags"] == "x y z"
