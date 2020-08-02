import os
from pathlib import Path

import yaml
from pkg_resources import parse_version

import pyodide_build.mkpkg

# Following tests make real network calls to the PyPi JSON API.
# Since the response is fully cached, and small, it is very fast and is
# unlikely to fail.


def test_mkpkg(tmpdir, monkeypatch):
    # TODO: parametrize to check version
    base_dir = Path(str(tmpdir))
    monkeypatch.setattr(pyodide_build.mkpkg, "PACKAGES_ROOT", base_dir)
    pyodide_build.mkpkg.make_package("idna")
    assert os.listdir(base_dir) == ["idna"]
    meta_path = base_dir / "idna" / "meta.yaml"
    assert meta_path.exists()

    with open(meta_path, "rb") as fh:
        db = yaml.safe_load(fh)

    assert db["package"]["name"] == "idna"
    assert db["source"]["url"].endswith(".tar.gz")


def test_mkpkg_update(tmpdir, monkeypatch):
    base_dir = Path(str(tmpdir))
    monkeypatch.setattr(pyodide_build.mkpkg, "PACKAGES_ROOT", base_dir)

    db_init = {
        "package": {"name": "idna", "version": "2.0"},
        "source": {
            "sha256": "b307872f855b18632ce0c21c5e45be78c0ea7ae4c15c828c20788b26921eb3f6",
            "url": "https://<some>/idna-2.0.tar.gz",
        },
        "test": {"imports": ["idna"], "custom": 2},
    }

    os.mkdir(base_dir / "idna")
    meta_path = base_dir / "idna" / "meta.yaml"
    with open(meta_path, "w") as fh:
        yaml.dump(db_init, fh)
    pyodide_build.mkpkg.update_package("idna")

    with open(meta_path, "rb") as fh:
        db = yaml.safe_load(fh)
    assert list(db.keys()) == list(db_init.keys())
    assert parse_version(db["package"]["version"]) > parse_version(
        db_init["package"]["version"]
    )
