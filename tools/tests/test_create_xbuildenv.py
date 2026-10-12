import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parents[1]))
from create_xbuildenv import _check_unisolated_packages_match_dist, create


def _write_lockfile(pyodide_root: Path, versions: dict[str, str]) -> None:
    lockfile = pyodide_root / "dist" / "pyodide-lock.json"
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    lockfile.write_text(
        json.dumps(
            {
                "packages": {
                    name: {"name": name, "version": version}
                    for name, version in versions.items()
                }
            }
        )
    )


def test_check_unisolated_packages_match_dist(tmp_path):
    _write_lockfile(tmp_path, {"numpy": "2.4.3", "scipy": "1.17.0"})

    _check_unisolated_packages_match_dist(
        tmp_path, {"numpy": "2.4.3", "scipy": "1.17.0"}
    )


def test_check_unisolated_packages_mismatched(tmp_path):
    # What ENABLE_PREBUILT_PACKAGES=1 produces when pyodide-recipes don't match
    # this repo
    _write_lockfile(tmp_path, {"numpy": "2.4.3", "scipy": "1.18.0"})

    with pytest.raises(ValueError, match="do not match the distribution"):
        _check_unisolated_packages_match_dist(
            tmp_path, {"numpy": "2.4.3", "scipy": "1.17.0"}
        )


def test_check_unisolated_packages_normalizes_names(tmp_path):
    _write_lockfile(tmp_path, {"ruamel.yaml": "0.18.6"})

    _check_unisolated_packages_match_dist(tmp_path, {"ruamel-yaml": "0.18.6"})


def test_check_unisolated_packages_missing_is_not_fatal(tmp_path, caplog):
    # A subset build egitimately omits packages.
    _write_lockfile(tmp_path, {"numpy": "2.4.3"})

    _check_unisolated_packages_match_dist(
        tmp_path, {"numpy": "2.4.3", "scipy": "1.17.0"}
    )

    assert "scipy" in caplog.text


def test_check_unisolated_packages_no_lockfile(tmp_path):
    with pytest.raises(FileNotFoundError):
        _check_unisolated_packages_match_dist(tmp_path, {"numpy": "2.4.3"})

    _check_unisolated_packages_match_dist(
        tmp_path, {"numpy": "2.4.3"}, skip_missing_files=True
    )


def test_xbuildenv_create(selenium, tmp_path):
    envpath = Path(tmp_path) / ".xbuildenv"
    root = Path(__file__).parents[2]

    create(envpath, root, skip_missing_files=True)

    assert (envpath / "xbuildenv").exists()
    assert (envpath / "xbuildenv" / "pyodide-root").is_dir()
    assert (envpath / "xbuildenv" / "site-packages-extras").is_dir()
    assert (envpath / "xbuildenv" / "requirements.txt").exists()

    # Test that the pins in requirements.txt exactly match the versions of the
    # xbuild packages in our recipes.
    from pyodide_build.recipe.loader import load_all_recipes

    expected = {
        name: config.package.version
        for name, config in load_all_recipes(root / "packages").items()
        if config.build.cross_build_env
    }
    requirements = (envpath / "xbuildenv" / "requirements.txt").read_text()
    pins = dict(line.split("==", 1) for line in requirements.split() if "==" in line)
    assert pins == expected

    # ...and the versions we actually ship, which may come from pyodide-recipes
    lockfile = envpath / "xbuildenv" / "pyodide-root" / "dist" / "pyodide-lock.json"
    shipped = json.loads(lockfile.read_text())["packages"]
    for name, version in pins.items():
        if name in shipped:
            assert shipped[name]["version"] == version
