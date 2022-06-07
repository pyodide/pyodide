import os
from pathlib import Path

import pytest
import yaml
from pkg_resources import parse_version

import pyodide_build.mkpkg
from pyodide_build.io import parse_package_config

# Following tests make real network calls to the PyPI JSON API.
# Since the response is fully cached, and small, it is very fast and is
# unlikely to fail.


@pytest.mark.parametrize("source_fmt", ["wheel", "sdist"])
def test_mkpkg(tmpdir, capsys, source_fmt):
    base_dir = Path(str(tmpdir))

    pyodide_build.mkpkg.make_package(base_dir, "idna", None, source_fmt)
    assert os.listdir(base_dir) == ["idna"]
    meta_path = base_dir / "idna" / "meta.yaml"
    assert meta_path.exists()
    captured = capsys.readouterr()
    assert f"Output written to {meta_path}" in captured.out

    db = parse_package_config(meta_path)

    assert db["package"]["name"] == "idna"
    if source_fmt == "wheel":
        assert db["source"]["url"].endswith(".whl")
    else:
        assert db["source"]["url"].endswith(".tar.gz")


@pytest.mark.parametrize("old_dist_type", ["wheel", "sdist"])
@pytest.mark.parametrize("new_dist_type", ["wheel", "sdist", "same"])
def test_mkpkg_update(tmpdir, old_dist_type, new_dist_type):
    base_dir = Path(str(tmpdir))

    old_ext = ".tar.gz" if old_dist_type == "sdist" else ".whl"
    old_url = "https://<some>/idna-2.0" + old_ext
    db_init: dict[str, dict[str, str | list[str]]] = {
        "package": {"name": "idna", "version": "2.0"},
        "source": {
            "sha256": "b307872f855b18632ce0c21c5e45be78c0ea7ae4c15c828c20788b26921eb3f6",
            "url": old_url,
        },
        "test": {"imports": ["idna"]},
    }

    package_dir = base_dir / "idna"
    package_dir.mkdir(parents=True)
    meta_path = package_dir / "meta.yaml"
    with open(meta_path, "w") as f:
        yaml.dump(db_init, f)
    source_fmt = new_dist_type
    if new_dist_type == "same":
        source_fmt = None
    pyodide_build.mkpkg.update_package(base_dir, "idna", None, False, source_fmt)

    db = parse_package_config(meta_path)
    assert list(db.keys()) == list(db_init.keys())
    assert parse_version(db["package"]["version"]) > parse_version(
        db_init["package"]["version"]  # type: ignore[arg-type]
    )
    if new_dist_type == "wheel":
        assert db["source"]["url"].endswith(".whl")
    elif new_dist_type == "sdist":
        assert db["source"]["url"].endswith(".tar.gz")
    else:
        assert db["source"]["url"].endswith(old_ext)
