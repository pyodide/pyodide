from functools import cache
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import yaml
from yaml import CLoader as Loader


def filter_info(info: dict[str, Any], browser: str) -> dict[str, Any]:
    # keep only flags related to the current browser
    suffix = "-" + browser
    result = {key.removesuffix(suffix): value for key, value in info.items()}
    if "skip" in info and f"skip{suffix}" in info:
        result["skip"] = info["skip"] + info[f"skip{suffix}"]
    return result


def possibly_skip_test(
    request: pytest.FixtureRequest,
    info: dict[str, Any],
    browser: str,
) -> dict[str, Any]:
    if "segfault" in info:
        pytest.skip(f"known segfault: {info['segfault']}")

    if "xfail" in info:
        reason = info["xfail"]
        if request.config.option.run_xfail:
            request.applymarker(
                pytest.mark.xfail(
                    run=False,
                    reason=f"known failure: {reason}",
                )
            )
        else:
            pytest.xfail(f"known failure: {reason}")

    if "xfail_browsers" in info and browser in info["xfail_browsers"]:
        reason = info["xfail_browsers"][browser]
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
    possibly_skip_test(request, info, selenium.browser)

    ignore_tests = info.get("skip", [])
    timeout = info.get("timeout", 30)
    if not isinstance(ignore_tests, list):
        raise Exception("Invalid python_tests.yaml entry: 'skip' should be a list")

    selenium.load_package(["test", "pydecimal"])
    selenium.set_script_timeout(timeout)
    try:
        res = selenium.run(
            dedent(
                f"""
                res = None
                import platform
                from test.libregrtest.main import main
                import sys
                sys.excepthook = sys.__excepthook__

                platform.platform(aliased=True)
                import _testcapi
                if hasattr(_testcapi, "raise_SIGINT_then_send_None"):
                    # This uses raise() which doesn't work.
                    del _testcapi.raise_SIGINT_then_send_None

                match_tests = [[pat, False] for pat in {ignore_tests}]
                try:
                    main(["{name}"], match_tests=match_tests, verbose=True, verbose3=True)
                except SystemExit as e:
                    if e.code == 4:
                        res = e.code
                    elif e.code != 0:
                        raise RuntimeError(f"Failed with code: {{e.code}}")
                res
                """
            )
        )
        if res == 4:
            pytest.skip("No tests ran")
    except selenium.JavascriptException:
        print(selenium.logs)
        raise


def get_test_info(test: dict[str, Any] | str) -> tuple[str, dict[str, Any]]:
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

    test_info = [get_test_info(test) for test in data]
    only_tests = []
    for [name, info] in test_info:
        if info.get("only"):
            only_tests.append((name, info))
    if only_tests:
        return only_tests
    return test_info


def pytest_generate_tests(metafunc):
    if "main_test" in metafunc.fixturenames:
        tests = get_tests()
        metafunc.parametrize(
            "main_test",
            [
                pytest.param(t, marks=pytest.mark.requires_dynamic_linking)
                for t in tests
            ],
            ids=[t[0] for t in tests],
        )
