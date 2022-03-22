from functools import cache
from pathlib import Path
from textwrap import dedent
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
        reason for (flag, reason) in info.items() if flag.startswith("segfault")
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
    if not isinstance(ignore_tests, list):
        raise Exception("Invalid python_tests.yaml entry: 'skip' should be a list")

    selenium.load_package(list(UNVENDORED_STDLIB_MODULES))
    try:
        selenium.run(
            dedent(
                f"""
            import platform
            from test import libregrtest

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
        )
    except selenium.JavascriptException:
        print(selenium.logs)
        raise


def get_test_info(test) -> tuple[str, dict[str, Any]]:
    if isinstance(test, dict):
        (name, info) = next(iter(test.items()))
    else:
        name = test
        info = {}
    return (name, info)


@cache
def get_tests() -> list[tuple[str, dict[str, Any]]]:
    with open(Path(__file__).parent / "python_tests.yaml") as file:
        data = yaml.load(file, Loader)

    return [get_test_info(test) for test in data]


def pytest_generate_tests(metafunc):
    if "main_test" in metafunc.fixturenames:
        tests = get_tests()
        metafunc.parametrize("main_test", tests, ids=[t[0] for t in tests])
