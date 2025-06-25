import functools
import os
from typing import Any, TypedDict

import pytest
from pyodide_lock import PyodideLockSpec

from conftest import PYODIDE_ROOT

PKG_DIR = PYODIDE_ROOT / "packages"


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
    "test-cpp-exceptions2": "Intentional",
    "matplotlib-inline": "circular dependency with IPython",
}

LOCKFILE_PATH = PYODIDE_ROOT / "dist" / "pyodide-lock.json"


class ImportTestCase(TypedDict):
    name: str
    imports: list[str]


def load_lockfile() -> PyodideLockSpec:
    try:
        return PyodideLockSpec.from_json(LOCKFILE_PATH)
    except Exception as e:
        raise FileNotFoundError(f"Failed to load lockfile from {LOCKFILE_PATH}") from e


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
    try:
        lockfile = load_lockfile()
    except FileNotFoundError:
        return [{"name": "no-lockfile-found"}]
    return generate_test_list(lockfile)


def idfn(testcase: ImportTestCase) -> str:
    # help pytest to display the name of the test case
    return testcase["name"]


@pytest.mark.skip_refcount_check
@pytest.mark.driver_timeout(120)
@pytest.mark.parametrize("testcase", build_testcases(), ids=idfn)
def test_import(selenium_standalone: Any, testcase: ImportTestCase) -> None:
    name = testcase["name"]
    if name == "no-lockfile-found":
        pytest.skip(f"Failed to load lockfile from {LOCKFILE_PATH}")
    imports = testcase["imports"]

    if name in XFAIL_PACKAGES:
        pytest.xfail(XFAIL_PACKAGES[name])

    if name in UNSUPPORTED_PACKAGES[selenium_standalone.browser]:
        pytest.xfail(
            f"{name} fails to load and is not supported on {selenium_standalone.browser}."
        )

    if not imports:
        # nothing to test
        return

    for import_name in imports:
        selenium_standalone.load_package([name])
        selenium_standalone.run(f"import {import_name}")
