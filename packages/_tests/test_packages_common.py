import functools
import os
from typing import TypedDict

import pytest
from pyodide_lock import PyodideLockSpec

from conftest import ROOT_PATH

PKG_DIR = ROOT_PATH / "packages"


UNSUPPORTED_PACKAGES: dict[str, list[str]] = {
    "chrome": [],
    "firefox": [],
    "safari": [],
    "node": ["cmyt", "yt", "galpy"],
}
if "CI" in os.environ:
    UNSUPPORTED_PACKAGES["chrome"].extend(["statsmodels"])

XFAIL_PACKAGES: dict[str, str] = {
    "soupsieve": "Importing soupsieve without installing beautifulsoup4 fails.",
}

lockfile_path = ROOT_PATH / "dist" / "pyodide-lock.json"


class ImportTestCase(TypedDict):
    name: str
    imports: list[str]


def load_lockfile() -> PyodideLockSpec:
    try:
        return PyodideLockSpec.from_json(lockfile_path)
    except Exception as e:
        raise Exception(f"Failed to load lockfile from {lockfile_path}") from e


def normalize_import_name(name: str) -> str:
    # TODO: normalize imports the pyodide-build side.
    return name.replace("-", "_").replace(".", "_")


def generate_test_list(lockfile: PyodideLockSpec) -> list[ImportTestCase]:
    packages = lockfile.packages
    testcases: list[ImportTestCase] = [
        {
            "name": package.name,
            "imports": [normalize_import_name(name) for name in package.imports],
        }
        for package in packages.values()
        if package.package_type in ("package", "cpython_module")
    ]

    return testcases


@functools.cache
def build_testcases():
    lockfile = load_lockfile()
    return generate_test_list(lockfile)


def idfn(testcase: ImportTestCase) -> str:
    # help pytest to display the name of the test case
    return testcase["name"]


@pytest.mark.skip_refcount_check
@pytest.mark.driver_timeout(120)
@pytest.mark.parametrize("testcase", build_testcases(), ids=idfn)
def test_import(selenium_standalone, testcase: ImportTestCase):
    name = testcase["name"]
    imports = testcase["imports"]

    if name in XFAIL_PACKAGES:
        pytest.xfail(XFAIL_PACKAGES[name])

    if name in UNSUPPORTED_PACKAGES[selenium_standalone.browser]:
        pytest.xfail(
            f"{name} fails to load and is not supported on {selenium_standalone.browser}."
        )

    if not imports:
        return

    for import_name in imports:
        selenium_standalone.load_package(name)
        selenium_standalone.run(f"import {import_name}")
