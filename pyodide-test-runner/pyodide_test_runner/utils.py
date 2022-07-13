import contextlib
import functools
import json
import re
from pathlib import Path

import pytest


@contextlib.contextmanager
def set_webdriver_script_timeout(selenium, script_timeout: float | None):
    """Set selenium script timeout

    Parameters
    ----------
    selenum : SeleniumWrapper
       a SeleniumWrapper wrapper instance
    script_timeout : int | float
       value of the timeout in seconds
    """
    if script_timeout is not None:
        selenium.set_script_timeout(script_timeout)
    yield
    # revert to the initial value
    if script_timeout is not None:
        selenium.set_script_timeout(selenium.script_timeout)


def parse_driver_timeout(node) -> float | None:
    """Parse driver timeout value from pytest request object"""
    mark = node.get_closest_marker("driver_timeout")
    if mark is None:
        return None
    else:
        return mark.args[0]


def parse_xfail_browsers(node) -> dict[str, str]:
    mark = node.get_closest_marker("xfail_browsers")
    if mark is None:
        return {}
    return mark.kwargs


def maybe_skip_test(item, dist_dir, delayed=False):
    """If necessary skip test at the fixture level, to avoid

    loading the selenium_standalone fixture which takes a long time.
    """
    browsers = "|".join(["firefox", "chrome", "node"])

    skip_msg = None
    # Testing a package. Skip the test if the package is not built.
    match = re.match(
        r".*/packages/(?P<name>[\w\-]+)/test_[\w\-]+\.py", str(item.parent.fspath)
    )
    if match:
        package_name = match.group("name")
        if not package_is_built(package_name, dist_dir) and re.match(
            rf"test_[\w\-]+\[({browsers})[^\]]*\]", item.name
        ):
            skip_msg = f"package '{package_name}' is not built."

    # Common package import test. Skip it if the package is not built.
    if (
        skip_msg is None
        and str(item.fspath).endswith("test_packages_common.py")
        and item.name.startswith("test_import")
    ):
        match = re.match(rf"test_import\[({browsers})-(?P<name>[\w-]+)\]", item.name)
        if match:
            package_name = match.group("name")
            if not package_is_built(package_name, dist_dir):
                # If the test is going to be skipped remove the
                # selenium_standalone as it takes a long time to initialize
                skip_msg = f"package '{package_name}' is not built."
        else:
            raise AssertionError(
                f"Couldn't parse package name from {item.name}. This should not happen!"
            )

    # TODO: also use this hook to skip doctests we cannot run (or run them
    # inside the selenium wrapper)

    if skip_msg is not None:
        if delayed:
            item.add_marker(pytest.mark.skip(reason=skip_msg))
        else:
            pytest.skip(skip_msg)


@functools.cache
def built_packages(dist_dir: Path) -> list[str]:
    """Returns the list of built package names from repodata.json"""
    repodata_path = dist_dir / "repodata.json"
    if not repodata_path.exists():
        return []
    return list(json.loads(repodata_path.read_text())["packages"].keys())


def package_is_built(package_name: str, dist_dir: Path) -> bool:
    return package_name.lower() in built_packages(dist_dir)
