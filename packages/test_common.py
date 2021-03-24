import pytest
import os
from pathlib import Path
from pyodide_build.common import _parse_package_subset
from pyodide_build.io import parse_package_config

PKG_DIR = Path(__file__).parent


def registered_packages():
    """Returns a list of registered package names"""
    packages = []
    for name in os.listdir(PKG_DIR):
        if (PKG_DIR / name).is_dir() and (PKG_DIR / name / "meta.yaml").exists():
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


UNSUPPORTED_PACKAGES: dict = {"chrome": [], "firefox": []}


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
@pytest.mark.parametrize("name", registered_packages())
def test_import(name, selenium_standalone):
    # check that we can parse the meta.yaml
    meta = parse_package_config(PKG_DIR / name / "meta.yaml")

    if name in UNSUPPORTED_PACKAGES[selenium_standalone.browser]:
        pytest.xfail(
            "{} fails to load and is not supported on {}.".format(
                name, selenium_standalone.browser
            )
        )

    built_packages = _parse_package_subset(os.environ.get("PYODIDE_PACKAGES"))
    # only a subset of packages were built
    if built_packages is not None and name not in built_packages:
        pytest.skip(f"{name} was skipped due to PYODIDE_PACKAGES")

    selenium_standalone.run("import glob, os")

    baseline_pyc = selenium_standalone.run(
        """
        len(list(glob.glob(
            '/lib/python3.8/site-packages/**/*.pyc',
            recursive=True)
        ))
        """
    )
    loaded_packages = []
    for import_name in meta.get("test", {}).get("imports", []):
        selenium_standalone.run_async("import %s" % import_name)
        # Make sure that even after importing, there are no additional .pyc
        # files
        assert (
            selenium_standalone.run(
                """
            len(list(glob.glob(
                '/lib/python3.8/site-packages/**/*.pyc',
                recursive=True)
            ))
            """
            )
            == baseline_pyc
        )
