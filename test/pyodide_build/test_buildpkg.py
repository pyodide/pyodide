import shutil
import subprocess

from pathlib import Path

from pyodide_build import buildpkg, common


def test_download_and_extract(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: True)
    monkeypatch.setattr(buildpkg, 'check_checksum', lambda *args, **kwargs: True)
    monkeypatch.setattr(shutil, 'unpack_archive', lambda *args, **kwargs: True)

    test_pkgs = []

    # tarballname == version
    test_pkgs.append(common.parse_package('./packages/numpy/meta.yaml'))
    test_pkgs.append(common.parse_package('./packages/scipy/meta.yaml'))

    # tarballname != version
    test_pkgs.append({
        'package': {'name': 'pyyaml', 'version': '5.3.1'},
        'source': {'url': 'https://-/PyYAML-5.3.1.tar.gz'}
    })

    for pkg in test_pkgs:
        packagedir = pkg['package']['name'] + '-' + pkg['package']['version']
        buildpath = Path(pkg['package']['name']) / 'build'
        srcpath = buildpkg.download_and_extract(buildpath, packagedir, pkg, args=None)

        assert srcpath.name in pkg['source']['url']

