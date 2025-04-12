import functools
import os
<<<<<<< HEAD
from typing import TypedDict
=======
from typing import Any, TypedDict
>>>>>>> upstream/main

import pytest
from pyodide_lock import PyodideLockSpec

<<<<<<< HEAD
from conftest import ROOT_PATH

PKG_DIR = ROOT_PATH / "packages"
=======
from conftest import PYODIDE_ROOT

PKG_DIR = PYODIDE_ROOT / "packages"
>>>>>>> upstream/main


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
    "cpp-exceptions-test2": "Intentional",
    "matplotlib-inline": "circular dependency with IPython",
}

<<<<<<< HEAD
lockfile_path = ROOT_PATH / "dist" / "pyodide-lock.json"


class TestCase(TypedDict):
=======
LOCKFILE_PATH = PYODIDE_ROOT / "dist" / "pyodide-lock.json"


class ImportTestCase(TypedDict):
>>>>>>> upstream/main
    name: str
    imports: list[str]


def load_lockfile() -> PyodideLockSpec:
    try:
<<<<<<< HEAD
        return PyodideLockSpec.from_json(lockfile_path)
    except Exception as e:
        raise Exception(f"Failed to load lockfile from {lockfile_path}") from e


def generate_test_list(lockfile: PyodideLockSpec) -> list[TestCase]:
    packages = lockfile.packages
    testcases: list[TestCase] = [
        {"name": package.name, "imports": package.imports}
=======
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
>>>>>>> upstream/main
        for package in packages.values()
        if package.package_type in ("package", "cpython_module")
    ]

    return testcases


@functools.cache
def build_testcases():
<<<<<<< HEAD
    lockfile = load_lockfile()
    return generate_test_list(lockfile)


def idfn(testcase):
=======
    try:
        lockfile = load_lockfile()
    except FileNotFoundError:
        return [{"name": "no-lockfile-found"}]
    return generate_test_list(lockfile)


def idfn(testcase: ImportTestCase) -> str:
>>>>>>> upstream/main
    # help pytest to display the name of the test case
    return testcase["name"]


@pytest.mark.skip_refcount_check
@pytest.mark.driver_timeout(120)
@pytest.mark.parametrize("testcase", build_testcases(), ids=idfn)
<<<<<<< HEAD
def test_import(selenium_standalone, testcase: TestCase):
    name = testcase["name"]
=======
def test_import(selenium_standalone: Any, testcase: ImportTestCase) -> None:
    name = testcase["name"]
    if name == "no-lockfile-found":
        pytest.skip(f"Failed to load lockfile from {LOCKFILE_PATH}")
>>>>>>> upstream/main
    imports = testcase["imports"]

    if name in XFAIL_PACKAGES:
        pytest.xfail(XFAIL_PACKAGES[name])

    if name in UNSUPPORTED_PACKAGES[selenium_standalone.browser]:
        pytest.xfail(
            f"{name} fails to load and is not supported on {selenium_standalone.browser}."
        )

    if not imports:
<<<<<<< HEAD
        return

    for import_name in imports:
        selenium_standalone.run_async(f"import {import_name}")
=======
        # nothing to test
        return

    for import_name in imports:
        selenium_standalone.load_package([name])
        selenium_standalone.run(f"import {import_name}")
>>>>>>> upstream/main
