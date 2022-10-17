import pytest
from typer.testing import CliRunner  # type: ignore[import]

from pyodide_build.cli import skeleton

runner = CliRunner()


@pytest.fixture
def packages_temp_path(tmp_path):
    yield tmp_path


def test_package(packages_temp_path):
    test_pkg = "pytest-pyodide"
    old_version = "0.21.0"
    new_version = "0.22.0"

    result = runner.invoke(
        skeleton.app,
        [
            "new",
            test_pkg,
            "--packages-dir",
            str(packages_temp_path),
            "--version",
            old_version,
        ],
    )
    assert result.exit_code == 0
    assert "pytest-pyodide/meta.yaml" in result.stdout

    result = runner.invoke(
        skeleton.app,
        [
            "update",
            test_pkg,
            "--packages-dir",
            str(packages_temp_path),
            "--version",
            new_version,
        ],
    )
    assert result.exit_code == 0
    assert f"Updated {test_pkg} from {old_version} to {new_version}" in result.stdout

    result = runner.invoke(
        skeleton.app, ["new", test_pkg, "--packages-dir", str(packages_temp_path)]
    )
    assert result.exit_code != 0
    assert "already exists" in str(result.exception)
