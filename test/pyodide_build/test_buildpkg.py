import shutil
import subprocess

from pathlib import Path

from pyodide_build import buildpkg, common


def test_download_and_extract(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: True)
    monkeypatch.setattr(buildpkg, "check_checksum", lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, "unpack_archive", lambda *args, **kwargs: True)

    test_pkgs = []

    # tarballname == version
    test_pkgs.append(common.parse_package("./packages/scipy/meta.yaml"))
    test_pkgs.append(common.parse_package("./packages/numpy/meta.yaml"))

    # tarballname != version
    test_pkgs.append(
        {
            "package": {"name": "pyyaml", "version": "5.3.1"},
            "source": {
                "url": "https://files.pythonhosted.org/packages/64/c2/b80047c7ac2478f9501676c988a5411ed5572f35d1beff9cae07d321512c/PyYAML-5.3.1.tar.gz"
            },
        }
    )

    for pkg in test_pkgs:
        packagedir = pkg["package"]["name"] + "-" + pkg["package"]["version"]
        buildpath = Path(pkg["package"]["name"]) / "build"
        srcpath = buildpkg.download_and_extract(buildpath, packagedir, pkg, args=None)

        assert srcpath.name.lower().endswith(packagedir.lower())
