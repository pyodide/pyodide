from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from yaml import CLoader as Loader

from pyodide_build.common import UNVENDORED_STDLIB_MODULES


def filter_info(info: dict[str, Any], browser: str) -> dict[str, Any]:
    info = dict(info)
    # keep only flags related to the current browser
    flags_to_remove = ["firefox", "chrome", "node"]
    flags_to_remove.remove(browser)
    for browser in flags_to_remove:
        for key in list(info.keys()):
            if key.endswith(browser):
                del info[key]
    return info


def possibly_skip_test(request, info: dict[str, Any]) -> dict[str, Any]:
    for reason in (
        reason for [flag, reason] in info.items() if flag.startswith("segfault")
    ):
        pytest.skip(f"known segfault: {reason}")

    for reason in (
        reason for [flag, reason] in info.items() if flag.startswith("xfail")
    ):
        if request.config.option.run_xfail:
            request.applymarker(
                pytest.mark.xfail(
                    run=False,
                    reason=f"known failure: {reason}",
                )
            )
        else:
            pytest.xfail(f"known failure: {reason}")
    return info


def test_cpython_core(main_test, selenium, request):
    [name, info] = main_test
    info = filter_info(info, selenium.browser)
    possibly_skip_test(request, info)

    ignore_tests = info.get("skip", [])

    selenium.load_package(UNVENDORED_STDLIB_MODULES)
    try:
        selenium.run(
            f"""
import asyncio
import os
import platform
import subprocess
import threading
from test import libregrtest
from unittest import SkipTest, TestCase, main
from unittest.mock import Mock, patch

platform.platform(aliased=True)
import _testcapi
if hasattr(_testcapi, "raise_SIGINT_then_send_None"):
    # This uses raise() which doesn't work.
    del _testcapi.raise_SIGINT_then_send_None

try:
    libregrtest.main(["{name}"], ignore_tests={ignore_tests}, verbose=True, verbose3=True)
except SystemExit as e:
    if e.code != 0:
        raise RuntimeError(f"Failed with code: {{e.code}}")
            """
        )
    except selenium.JavascriptException:
        print(selenium.logs)
        raise


def get_test_info(test):
    if isinstance(test, dict):
        [name, info] = next(iter(test.items()))
    else:
        name = test
        info = {}
    return [name, info]


@cache
def get_tests():
    with open(Path(__file__).parent / "python_tests.yaml") as file:
        data = yaml.load(file, Loader)

    return {name: info for test in data for [name, info] in [get_test_info(test)]}


def pytest_generate_tests(metafunc):
    if "main_test" in metafunc.fixturenames:
        tests = get_tests()
        metafunc.parametrize("main_test", tests.items(), ids=tests.keys())
