import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from ..common import chdir


@pytest.fixture(scope="module")
def temp_python_lib(tmp_path_factory):
    libdir = tmp_path_factory.mktemp("python")

    path = Path(libdir)

    (path / "test").mkdir()
    (path / "test" / "test_blah.py").touch()
    (path / "distutils").mkdir()
    (path / "turtle.py").touch()

    (path / "module1.py").touch()
    (path / "module2.py").touch()

    (path / "hello_pyodide.py").write_text("def hello(): return 'hello'")

    yield libdir


def mock_repodata_json() -> dict[str, Any]:
    # TODO: use pydantic

    return {
        "info": {
            "version": "0.22.1",
        },
        "packages": {},
    }


@pytest.fixture(scope="module")
def temp_xbuildenv(tmp_path_factory):
    """
    Create a temporary xbuildenv archive
    """
    base = tmp_path_factory.mktemp("base")

    path = Path(base)

    xbuildenv = path / "xbuildenv"
    xbuildenv.mkdir()

    pyodide_root = xbuildenv / "pyodide-root"
    site_packages_extra = xbuildenv / "site-packages-extras"
    requirements_txt = xbuildenv / "requirements.txt"

    pyodide_root.mkdir()
    site_packages_extra.mkdir()
    requirements_txt.touch()

    (pyodide_root / "Makefile.envs").write_text(
        """
export HOSTSITEPACKAGES=$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages

.output_vars:
	set
"""
    )
    (pyodide_root / "dist").mkdir()
    (pyodide_root / "dist" / "repodata.json").write_text(
        json.dumps(mock_repodata_json())
    )

    with chdir(base):
        archive_name = shutil.make_archive("xbuildenv", "tar")

    yield base, archive_name
