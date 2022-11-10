import os
import shutil
from pathlib import Path

from typer.testing import CliRunner  # type: ignore[import]

from pyodide_build import common
from pyodide_build.cli import build, skeleton

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


def test_build_recipe(tmp_path, monkeypatch):
    output_dir = tmp_path / "dist"
    recipe_dir = Path(__file__).parent / "_test_recipes"

    pkgs = {
        "pkg_test_graph1": {"pkg_test_graph2"},
        "pkg_test_graph3": {},
    }

    pkgs_to_build = pkgs.keys() | {p for v in pkgs.values() for p in v}

    monkeypatch.setattr(common, "ALWAYS_PACKAGES", {})

    for build_dir in recipe_dir.rglob("build"):
        shutil.rmtree(build_dir)

    result = runner.invoke(
        build.app,
        [
            "recipe",
            *pkgs.keys(),
            "--recipe-dir",
            recipe_dir,
            "--output",
            output_dir,
        ],
    )

    assert result.exit_code == 0, result.stdout

    for pkg in pkgs_to_build:
        assert f"built {pkg} in" in result.stdout

    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == len(pkgs_to_build)


def test_fetch_or_build_pypi(tmp_path):
    output_dir = tmp_path / "dist"
    # one pure-python package (doesn't need building) and one sdist package (needs building)
    pkgs = ["pytest-pyodide", "pycryptodome==3.15.0"]

    os.chdir(tmp_path)
    for p in pkgs:
        result = runner.invoke(
            build.app,
            ["pypi", p],
        )
        assert result.exit_code == 0, result.stdout

    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == len(pkgs)
