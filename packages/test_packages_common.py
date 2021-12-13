import pytest
import os
from pathlib import Path
from typing import List
import functools
import packaging.utils

from pyodide_build.io import parse_package_config

PKG_DIR = Path(__file__).parent
BUILD_DIR = PKG_DIR.parent / "build"


@functools.cache
def registered_packages() -> List[str]:
    """Returns a list of registered package names"""
    packages = []
    for name in os.listdir(PKG_DIR):
        if (PKG_DIR / name).is_dir() and (PKG_DIR / name / "meta.yaml").exists():
            packages.append(name)
    return packages


@functools.cache
def registered_packages_lowercase() -> List[str]:
    """Returns a list of lowercased registered package names"""
    return [name.lower() for name in registered_packages()]


@functools.cache
def built_packages() -> List[str]:
    """Returns a list of built package names.

    This functions lists the names of the .data files in the build/ directory.
    """
    if not BUILD_DIR.exists():
        return []
    registered_packages_list = registered_packages_lowercase()
    registered_packages_ = set(registered_packages_list)
    for x in registered_packages_list:
        registered_packages_.add(x.replace("_", "-"))

    packages = []
    for fpath in os.listdir(BUILD_DIR):
        if not fpath.endswith(".whl") and not fpath.endswith(".tar"):
            continue
        if fpath.endswith(".whl"):
            name = str(packaging.utils.parse_wheel_filename(fpath)[0])
        else:
            name = fpath.partition("-")[0]
        if name in registered_packages_:
            packages.append(name)
    return packages


def registered_packages_meta():
    """Returns a dictionary with the contents of `meta.yaml`
    for each registered package
    """
    packages = registered_packages
    return {
        name: parse_package_config(PKG_DIR / name / "meta.yaml") for name in packages
    }


UNSUPPORTED_PACKAGES: dict = {
    "chrome": ["scikit-image", "statsmodels"],
    "firefox": [],
    "node": ["scikit-image", "statsmodels"],
}


@pytest.mark.parametrize("name", registered_packages())
def test_parse_package(name):
    # check that we can parse the meta.yaml
    meta = parse_package_config(PKG_DIR / name / "meta.yaml")

    skip_host = meta.get("build", {}).get("skip_host", True)
    if name == "numpy":
        assert skip_host is False
    elif name == "pandas":
        assert skip_host is True


@pytest.mark.skip_refcount_check
@pytest.mark.driver_timeout(40)
@pytest.mark.parametrize("name", registered_packages())
def test_import(name, selenium_standalone):
    if name.lower().replace("_", "-") not in built_packages():
        print(name, sorted(built_packages()))
        raise AssertionError(
            "Implementation error. Test for an unbuilt package "
            "should have been skipped in selenium_standalone fixture"
        )

    meta = parse_package_config(PKG_DIR / name / "meta.yaml")

    if name in UNSUPPORTED_PACKAGES[selenium_standalone.browser]:
        pytest.xfail(
            "{} fails to load and is not supported on {}.".format(
                name, selenium_standalone.browser
            )
        )

    selenium_standalone.run("import glob, os")

    baseline_pyc = selenium_standalone.run(
        """
        len(list(glob.glob(
            '/lib/python3.9/site-packages/**/*.pyc',
            recursive=True)
        ))
        """
    )
    for import_name in meta.get("test", {}).get("imports", []):
        selenium_standalone.run_async("import %s" % import_name)
        # Make sure that even after importing, there are no additional .pyc
        # files
        assert (
            selenium_standalone.run(
                """
            len(list(glob.glob(
                '/lib/python3.9/site-packages/**/*.pyc',
                recursive=True)
            ))
            """
            )
            == baseline_pyc
        )
