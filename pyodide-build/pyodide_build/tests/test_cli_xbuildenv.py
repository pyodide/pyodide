from pathlib import Path

from typer.testing import CliRunner

from pyodide_build.cli import (
    xbuildenv,
)

runner = CliRunner()


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


def test_xbuildenv_install(tmp_path, mock_xbuildenv_url):
    envpath = Path(tmp_path) / ".xbuildenv"

    result = runner.invoke(
        xbuildenv.app,
        [
            "install",
            "--path",
            str(envpath),
            "--url",
            mock_xbuildenv_url,
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Downloading Pyodide cross-build environment" in result.stdout, result.stdout
    assert "Installing Pyodide cross-build environment" in result.stdout, result.stdout
    assert (envpath / "xbuildenv").is_symlink()
    assert (envpath / "xbuildenv").resolve().exists()

    concrete_path = (envpath / "xbuildenv").resolve()
    assert (concrete_path / ".installed").exists()


def test_xbuildenv_version(tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"

    (envpath / "0.25.0").mkdir(exist_ok=True, parents=True)
    (envpath / "0.25.1").mkdir(exist_ok=True, parents=True)
    (envpath / "0.26.0").mkdir(exist_ok=True, parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.26.0")

    result = runner.invoke(
        xbuildenv.app,
        [
            "version",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "0.26.0" in result.stdout, result.stdout


def test_xbuildenv_versions(tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"

    (envpath / "0.25.0").mkdir(exist_ok=True, parents=True)
    (envpath / "0.25.1").mkdir(exist_ok=True, parents=True)
    (envpath / "0.26.0").mkdir(exist_ok=True, parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.26.0")

    result = runner.invoke(
        xbuildenv.app,
        [
            "versions",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "  0.25.0" in result.stdout, result.stdout
    assert "  0.25.1" in result.stdout, result.stdout
    assert "* 0.26.0" in result.stdout, result.stdout


def test_xbuildenv_use(tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"

    (envpath / "0.25.0").mkdir(exist_ok=True, parents=True)
    (envpath / "0.25.1").mkdir(exist_ok=True, parents=True)
    (envpath / "0.26.0").mkdir(exist_ok=True, parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.26.0")

    result = runner.invoke(
        xbuildenv.app,
        [
            "use",
            "0.25.0",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (
        "Pyodide cross-build environment 0.25.0 is now in use" in result.stdout
    ), result.stdout


def test_xbuildenv_uninstall(tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"

    (envpath / "0.25.0").mkdir(exist_ok=True, parents=True)
    (envpath / "0.25.1").mkdir(exist_ok=True, parents=True)
    (envpath / "0.26.0").mkdir(exist_ok=True, parents=True)
    (envpath / "xbuildenv").symlink_to(envpath / "0.26.0")

    result = runner.invoke(
        xbuildenv.app,
        [
            "uninstall",
            "0.25.0",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (
        "Pyodide cross-build environment 0.25.0 uninstalled" in result.stdout
    ), result.stdout

    result = runner.invoke(
        xbuildenv.app,
        [
            "uninstall",
            "0.26.0",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (
        "Pyodide cross-build environment 0.26.0 uninstalled" in result.stdout
    ), result.stdout

    result = runner.invoke(
        xbuildenv.app,
        [
            "uninstall",
            "0.26.1",
            "--path",
            str(envpath),
        ],
    )

    assert result.exit_code != 0, result.stdout
    assert isinstance(result.exception, ValueError), result.exception
