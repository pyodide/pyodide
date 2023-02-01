# flake8: noqa

import os
import shutil
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner  # type: ignore[import]

from pyodide_build import common
from pyodide_build.cli import build, build_recipes, config, create_zipfile, skeleton

from .fixture import temp_python_lib

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


def test_build_recipe(selenium, tmp_path, monkeypatch, request):
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

    assert result.stdout.strip() == common.get_make_flag(env_var)


def test_create_zipfile(temp_python_lib, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    app = typer.Typer()
    app.command()(create_zipfile.main)

    result = runner.invoke(
        app,
        [
            str(temp_python_lib),
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


def test_create_zipfile_compile(temp_python_lib, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    app = typer.Typer()
    app.command()(create_zipfile.main)

    result = runner.invoke(
        app,
        [
            str(temp_python_lib),
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
