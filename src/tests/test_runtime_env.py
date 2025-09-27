"""Tests for RuntimeEnv singleton pattern and runtime detection."""

import pytest
from pytest_pyodide import run_in_pyodide


@pytest.fixture
def runtime_flags():
    """Runtime environment flags."""
    return [
        "IN_NODE",
        "IN_BROWSER",
        "IN_DENO",
        "IN_BUN",
        "IN_BROWSER_MAIN_THREAD",
        "IN_BROWSER_WEB_WORKER",
        "IN_NODE_COMMONJS",
        "IN_NODE_ESM",
        "IN_SAFARI",
        "IN_SHELL",
    ]


class TestRuntimeEnvBasic:
    """Basic RuntimeEnv tests."""

    def test_runtime_env_import(self, selenium, runtime_flags):
        @run_in_pyodide
        def run(selenium, runtime_flags):
            from pyodide_js import RUNTIME_ENV

            for flag in runtime_flags:
                assert hasattr(RUNTIME_ENV, flag), (
                    f"RUNTIME_ENV should have {flag} attribute"
                )
                flag_value = getattr(RUNTIME_ENV, flag)
                assert isinstance(flag_value, bool), (
                    f"{flag} should be boolean, got {type(flag_value)}"
                )

        run(selenium, runtime_flags)

    def test_runtime_env_consistency(self, selenium):
        @run_in_pyodide
        def run(selenium):
            from pyodide_js import RUNTIME_ENV

            # Test mutual exclusivity of main runtime types
            runtime_count = sum(
                [RUNTIME_ENV.IN_NODE, RUNTIME_ENV.IN_DENO, RUNTIME_ENV.IN_BUN]
            )

            # Should be in exactly one main runtime (Node, Deno, Bun) or browser
            if RUNTIME_ENV.IN_BROWSER:
                assert runtime_count == 0, "Cannot be both browser and server runtime"
            else:
                assert runtime_count == 1, (
                    f"Should be in exactly one server runtime, got {runtime_count}"
                )

            # Test browser sub-flags
            if RUNTIME_ENV.IN_BROWSER:
                thread_count = sum(
                    [
                        RUNTIME_ENV.IN_BROWSER_MAIN_THREAD,
                        RUNTIME_ENV.IN_BROWSER_WEB_WORKER,
                    ]
                )
                assert thread_count <= 1, "Cannot be both main thread and web worker"

            # Test Node.js sub-flags
            if RUNTIME_ENV.IN_NODE:
                node_type_count = sum(
                    [RUNTIME_ENV.IN_NODE_COMMONJS, RUNTIME_ENV.IN_NODE_ESM]
                )
                assert node_type_count <= 1, "Cannot be both CommonJS and ESM"

        run(selenium)


class TestRuntimeEnvironmentDetection:
    """Runtime environment detection tests."""

    def test_browser_environment_detection(self, selenium):
        @run_in_pyodide
        def run(selenium):
            from pyodide_js import RUNTIME_ENV

            # Check if we're actually in browser environment
            if RUNTIME_ENV.IN_BROWSER:
                # Browser-specific assertions
                assert not RUNTIME_ENV.IN_NODE, "Should not detect Node.js in browser"
                assert not RUNTIME_ENV.IN_DENO, "Should not detect Deno in browser"
                assert not RUNTIME_ENV.IN_BUN, "Should not detect Bun in browser"
                assert not RUNTIME_ENV.IN_SHELL, "Should not detect Shell in browser"

                # Should be either main thread or web worker
                thread_check = (
                    RUNTIME_ENV.IN_BROWSER_MAIN_THREAD
                    or RUNTIME_ENV.IN_BROWSER_WEB_WORKER
                )
                assert thread_check, (
                    "Browser should be either main thread or web worker"
                )
            else:
                # If not in browser, just verify the detection is consistent
                assert (
                    RUNTIME_ENV.IN_NODE
                    or RUNTIME_ENV.IN_DENO
                    or RUNTIME_ENV.IN_BUN
                    or RUNTIME_ENV.IN_SHELL
                ), "Should be in some runtime environment"

        run(selenium)

    def test_node_environment_detection(self, selenium):
        @run_in_pyodide
        def run(selenium):
            from pyodide_js import RUNTIME_ENV

            # Check if we're actually in Node.js environment
            if RUNTIME_ENV.IN_NODE:
                # Node.js-specific assertions
                assert not RUNTIME_ENV.IN_BROWSER, (
                    "Should not detect browser in Node.js"
                )
                assert not RUNTIME_ENV.IN_DENO, "Should not detect Deno in Node.js"
                assert not RUNTIME_ENV.IN_BUN, "Should not detect Bun in Node.js"
                assert not RUNTIME_ENV.IN_SHELL, "Should not detect Shell in Node.js"

                # Should be either CommonJS or ESM
                assert RUNTIME_ENV.IN_NODE_COMMONJS or RUNTIME_ENV.IN_NODE_ESM, (
                    "Node.js should be either CommonJS or ESM"
                )
            else:
                # If not in Node.js, just verify the detection is consistent
                assert (
                    RUNTIME_ENV.IN_BROWSER
                    or RUNTIME_ENV.IN_DENO
                    or RUNTIME_ENV.IN_BUN
                    or RUNTIME_ENV.IN_SHELL
                ), "Should be in some runtime environment"

        run(selenium)

    def test_shell_environment_detection(self, selenium):
        @run_in_pyodide
        def run(selenium):
            from pyodide_js import RUNTIME_ENV

            # Check if we're actually in Shell environment
            if RUNTIME_ENV.IN_SHELL:
                # Shell-specific assertions
                assert not RUNTIME_ENV.IN_BROWSER, "Should not detect browser in Shell"
                assert not RUNTIME_ENV.IN_NODE, "Should not detect Node.js in Shell"
                assert not RUNTIME_ENV.IN_DENO, "Should not detect Deno in Shell"
                assert not RUNTIME_ENV.IN_BUN, "Should not detect Bun in Shell"

                # Shell-specific flags should be false
                assert not RUNTIME_ENV.IN_NODE_COMMONJS, "Shell should not be CommonJS"
                assert not RUNTIME_ENV.IN_NODE_ESM, "Shell should not be Node ESM"
                assert not RUNTIME_ENV.IN_BROWSER_MAIN_THREAD, (
                    "Shell should not be browser main thread"
                )
                assert not RUNTIME_ENV.IN_BROWSER_WEB_WORKER, (
                    "Shell should not be web worker"
                )
            else:
                # If not in Shell, just verify the detection is consistent
                assert (
                    RUNTIME_ENV.IN_BROWSER
                    or RUNTIME_ENV.IN_NODE
                    or RUNTIME_ENV.IN_DENO
                    or RUNTIME_ENV.IN_BUN
                ), "Should be in some runtime environment"

        run(selenium)


class TestWebWorkerEnvironment:
    """Web worker environment tests."""

    @pytest.mark.xfail_browsers(safari="safari web workers are flaky")
    def test_webworker_runtime_env(self, selenium_webworker_standalone):
        """Test web worker RUNTIME_ENV detection."""
        selenium_webworker_standalone.run_webworker("""
            from pyodide_js import RUNTIME_ENV

            # This should work in web worker (matches existing test)
            assert RUNTIME_ENV.IN_BROWSER_WEB_WORKER is True
            assert RUNTIME_ENV.IN_BROWSER is True
            assert RUNTIME_ENV.IN_BROWSER_MAIN_THREAD is False
            assert RUNTIME_ENV.IN_NODE is False
        """)
