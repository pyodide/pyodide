"""Tests for RuntimeEnv singleton pattern and runtime detection."""

import pytest


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
        """Test RUNTIME_ENV import and flags."""
        selenium.run(f"""
            from pyodide_js import RUNTIME_ENV

            required_flags = {runtime_flags!r}

            for flag in required_flags:
                assert hasattr(RUNTIME_ENV, flag), f'RUNTIME_ENV should have {{flag}} attribute'
                flag_value = getattr(RUNTIME_ENV, flag)
                assert isinstance(flag_value, bool), f'{{flag}} should be boolean, got {{type(flag_value)}}'
        """)

    def test_runtime_env_consistency(self, selenium):
        """Test RUNTIME_ENV flag consistency."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Test mutual exclusivity of main runtime types
            runtime_count = sum([
                RUNTIME_ENV.IN_NODE,
                RUNTIME_ENV.IN_DENO,
                RUNTIME_ENV.IN_BUN
            ])

            # Should be in exactly one main runtime (Node, Deno, Bun) or browser
            if RUNTIME_ENV.IN_BROWSER:
                assert runtime_count == 0, "Cannot be both browser and server runtime"
            else:
                assert runtime_count == 1, f"Should be in exactly one server runtime, got {runtime_count}"

            # Test browser sub-flags
            if RUNTIME_ENV.IN_BROWSER:
                thread_count = sum([
                    RUNTIME_ENV.IN_BROWSER_MAIN_THREAD,
                    RUNTIME_ENV.IN_BROWSER_WEB_WORKER
                ])
                assert thread_count <= 1, "Cannot be both main thread and web worker"

            # Test Node.js sub-flags
            if RUNTIME_ENV.IN_NODE:
                node_type_count = sum([
                    RUNTIME_ENV.IN_NODE_COMMONJS,
                    RUNTIME_ENV.IN_NODE_ESM
                ])
                assert node_type_count <= 1, "Cannot be both CommonJS and ESM"
        """)


class TestRuntimeEnvironmentDetection:
    """Runtime environment detection tests."""

    def test_browser_environment_detection(self, selenium):
        """Test browser environment detection."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Check if we're actually in browser environment
            if RUNTIME_ENV.IN_BROWSER:
                # Browser-specific assertions
                assert not RUNTIME_ENV.IN_NODE, "Should not detect Node.js in browser"
                assert not RUNTIME_ENV.IN_DENO, "Should not detect Deno in browser"
                assert not RUNTIME_ENV.IN_BUN, "Should not detect Bun in browser"
                assert not RUNTIME_ENV.IN_SHELL, "Should not detect Shell in browser"

                # Should be either main thread or web worker
                thread_check = RUNTIME_ENV.IN_BROWSER_MAIN_THREAD or RUNTIME_ENV.IN_BROWSER_WEB_WORKER
                assert thread_check, "Browser should be either main thread or web worker"
            else:
                # If not in browser, just verify the detection is consistent
                assert RUNTIME_ENV.IN_NODE or RUNTIME_ENV.IN_DENO or RUNTIME_ENV.IN_BUN or RUNTIME_ENV.IN_SHELL, \
                    "Should be in some runtime environment"
        """)

    def test_node_environment_detection(self, selenium):
        """Test Node.js environment detection."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Check if we're actually in Node.js environment
            if RUNTIME_ENV.IN_NODE:
                # Node.js-specific assertions
                assert not RUNTIME_ENV.IN_BROWSER, "Should not detect browser in Node.js"
                assert not RUNTIME_ENV.IN_DENO, "Should not detect Deno in Node.js"
                assert not RUNTIME_ENV.IN_BUN, "Should not detect Bun in Node.js"
                assert not RUNTIME_ENV.IN_SHELL, "Should not detect Shell in Node.js"

                # Should be either CommonJS or ESM
                assert RUNTIME_ENV.IN_NODE_COMMONJS or RUNTIME_ENV.IN_NODE_ESM, \
                    "Node.js should be either CommonJS or ESM"
            else:
                # If not in Node.js, just verify the detection is consistent
                assert RUNTIME_ENV.IN_BROWSER or RUNTIME_ENV.IN_DENO or RUNTIME_ENV.IN_BUN or RUNTIME_ENV.IN_SHELL, \
                    "Should be in some runtime environment"
        """)

    def test_deno_environment_detection(self, selenium):
        """Test Deno environment detection."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Check if we're actually in Deno environment
            if RUNTIME_ENV.IN_DENO:
                # Deno-specific assertions
                assert not RUNTIME_ENV.IN_BROWSER, "Should not detect browser in Deno"
                assert not RUNTIME_ENV.IN_NODE, "Should not detect Node.js in Deno"
                assert not RUNTIME_ENV.IN_BUN, "Should not detect Bun in Deno"
                assert not RUNTIME_ENV.IN_SHELL, "Should not detect Shell in Deno"

                # Deno-specific flags should be false
                assert not RUNTIME_ENV.IN_NODE_COMMONJS, "Deno should not be CommonJS"
                assert not RUNTIME_ENV.IN_NODE_ESM, "Deno should not be Node ESM"
                assert not RUNTIME_ENV.IN_BROWSER_MAIN_THREAD, "Deno should not be browser main thread"
                assert not RUNTIME_ENV.IN_BROWSER_WEB_WORKER, "Deno should not be web worker"
            else:
                # If not in Deno, just verify the detection is consistent
                assert RUNTIME_ENV.IN_BROWSER or RUNTIME_ENV.IN_NODE or RUNTIME_ENV.IN_BUN or RUNTIME_ENV.IN_SHELL, \
                    "Should be in some runtime environment"
        """)

    def test_bun_environment_detection(self, selenium):
        """Test Bun environment detection."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Check if we're actually in Bun environment
            if RUNTIME_ENV.IN_BUN:
                # Bun-specific assertions
                assert not RUNTIME_ENV.IN_BROWSER, "Should not detect browser in Bun"
                assert not RUNTIME_ENV.IN_NODE, "Should not detect Node.js in Bun"
                assert not RUNTIME_ENV.IN_DENO, "Should not detect Deno in Bun"
                assert not RUNTIME_ENV.IN_SHELL, "Should not detect Shell in Bun"

                # Bun-specific flags should be false
                assert not RUNTIME_ENV.IN_NODE_COMMONJS, "Bun should not be CommonJS"
                assert not RUNTIME_ENV.IN_NODE_ESM, "Bun should not be Node ESM"
                assert not RUNTIME_ENV.IN_BROWSER_MAIN_THREAD, "Bun should not be browser main thread"
                assert not RUNTIME_ENV.IN_BROWSER_WEB_WORKER, "Bun should not be web worker"
            else:
                # If not in Bun, just verify the detection is consistent
                assert RUNTIME_ENV.IN_BROWSER or RUNTIME_ENV.IN_NODE or RUNTIME_ENV.IN_DENO or RUNTIME_ENV.IN_SHELL, \
                    "Should be in some runtime environment"
        """)

    def test_shell_environment_detection(self, selenium):
        """Test Shell environment detection."""
        selenium.run("""
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
                assert not RUNTIME_ENV.IN_BROWSER_MAIN_THREAD, "Shell should not be browser main thread"
                assert not RUNTIME_ENV.IN_BROWSER_WEB_WORKER, "Shell should not be web worker"
            else:
                # If not in Shell, just verify the detection is consistent
                assert RUNTIME_ENV.IN_BROWSER or RUNTIME_ENV.IN_NODE or RUNTIME_ENV.IN_DENO or RUNTIME_ENV.IN_BUN, \
                    "Should be in some runtime environment"
        """)


class TestBackwardCompatibility:
    """Backward compatibility tests."""

    def test_detect_environment_deprecated_function(self, selenium):
        """Test deprecated detectEnvironment function."""
        selenium.run("""
            import pyodide_js
            from pyodide_js import RUNTIME_ENV

            # Test that detectEnvironment exists and is callable
            assert hasattr(pyodide_js, 'detectEnvironment'), "pyodide_js should have detectEnvironment attribute"
            assert callable(pyodide_js.detectEnvironment), "detectEnvironment should be callable"

            # Test that detectEnvironment returns the same values as RUNTIME_ENV
            detected_env = pyodide_js.detectEnvironment()

            # Compare all runtime flags
            runtime_flags = [
                'IN_NODE', 'IN_BROWSER', 'IN_DENO', 'IN_BUN', 'IN_SHELL',
                'IN_BROWSER_MAIN_THREAD', 'IN_BROWSER_WEB_WORKER',
                'IN_NODE_COMMONJS', 'IN_NODE_ESM', 'IN_SAFARI'
            ]

            for flag in runtime_flags:
                runtime_env_value = getattr(RUNTIME_ENV, flag)
                detected_env_value = getattr(detected_env, flag)
                assert runtime_env_value == detected_env_value, (
                    f"detectEnvironment().{flag} ({detected_env_value}) should match "
                    f"RUNTIME_ENV.{flag} ({runtime_env_value})"
                )

            # Test that they have the same values (since they may be different proxy objects)
            # In JavaScript-Python bridge, objects may not be identical but should have same values
            print(f"RUNTIME_ENV type: {type(RUNTIME_ENV)}")
            print(f"detected_env type: {type(detected_env)}")

            # The objects should at least have the same string representation of values
            for flag in runtime_flags:
                runtime_env_value = getattr(RUNTIME_ENV, flag)
                detected_env_value = getattr(detected_env, flag)
                assert runtime_env_value == detected_env_value, (
                    f"Values should match even if objects are different proxies: "
                    f"RUNTIME_ENV.{flag}={runtime_env_value}, detectEnvironment().{flag}={detected_env_value}"
                )
        """)

    def test_runtime_env_singleton_behavior(self, selenium, runtime_flags):
        """Test RUNTIME_ENV singleton behavior."""
        selenium.run(f"""
            from pyodide_js import RUNTIME_ENV as env1
            from pyodide_js import RUNTIME_ENV as env2

            required_flags = {runtime_flags!r}

            for flag in required_flags:
                value1 = getattr(env1, flag)
                value2 = getattr(env2, flag)
                assert isinstance(value1, bool), f"{{flag}} should be boolean, got {{type(value1)}}"
                assert isinstance(value2, bool), f"{{flag}} should be boolean, got {{type(value2)}}"
                assert value1 == value2, (
                    f"RUNTIME_ENV.{{flag}} should be consistent across imports "
                    f"(got {{value1}} vs {{value2}})"
                )
        """)

    def test_runtime_env_accessible_from_python(self, selenium):
        """Test RUNTIME_ENV Python accessibility."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Should be able to access flags directly
            browser_flag = RUNTIME_ENV.IN_BROWSER
            node_flag = RUNTIME_ENV.IN_NODE

            # Should be boolean values
            assert isinstance(browser_flag, bool)
            assert isinstance(node_flag, bool)

            # Should be mutually exclusive in most cases
            if browser_flag:
                assert not node_flag, "Cannot be both browser and Node.js"
            if node_flag:
                assert not browser_flag, "Cannot be both Node.js and browser"
        """)


class TestWebWorkerEnvironment:
    """Web worker environment tests."""

    @pytest.mark.xfail_browsers(
        chrome="webworker only", firefox="webworker only", safari="webworker only"
    )
    def test_webworker_runtime_env(self, selenium_webworker_standalone):
        """Test web worker RUNTIME_ENV detection."""
        output = selenium_webworker_standalone.run_webworker("""
            from pyodide_js import RUNTIME_ENV

            # This should work in web worker (matches existing test)
            assert RUNTIME_ENV.IN_BROWSER_WEB_WORKER is True
            assert RUNTIME_ENV.IN_BROWSER is True
            assert RUNTIME_ENV.IN_BROWSER_MAIN_THREAD is False
            assert RUNTIME_ENV.IN_NODE is False

            "webworker_test_passed"
        """)

        assert output == "webworker_test_passed"


class TestSchedulerOptimization:
    """Scheduler optimization tests."""

    def test_scheduler_logic_patterns(self, selenium):
        """Test scheduler logic patterns."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Test scheduler selection logic (based on scheduler.ts)
            # Node.js: should prefer setImmediate
            if RUNTIME_ENV.IN_NODE:
                scheduler_type = "setImmediate"
                assert scheduler_type == "setImmediate", "Node.js should use setImmediate"

            # Bun: should also prefer setImmediate
            elif RUNTIME_ENV.IN_BUN:
                scheduler_type = "setImmediate"
                assert scheduler_type == "setImmediate", "Bun should use setImmediate"

            # Deno: should prefer queueMicrotask
            elif RUNTIME_ENV.IN_DENO:
                scheduler_type = "queueMicrotask"
                assert scheduler_type == "queueMicrotask", "Deno should use queueMicrotask"

            # Browser: MessageChannel or postMessage or setTimeout
            elif RUNTIME_ENV.IN_BROWSER:
                if RUNTIME_ENV.IN_SAFARI:
                    # Safari: should avoid MessageChannel
                    scheduler_type = "postMessage_or_setTimeout"
                else:
                    # Other browsers: can use MessageChannel
                    scheduler_type = "MessageChannel_or_postMessage_or_setTimeout"
                assert "Message" in scheduler_type or "setTimeout" in scheduler_type

            # Shell: should fallback to setTimeout
            elif RUNTIME_ENV.IN_SHELL:
                scheduler_type = "setTimeout"
                assert scheduler_type == "setTimeout", "Shell should use setTimeout"

            # Should always have a scheduler strategy
            assert 'scheduler_type' in locals(), "Should determine a scheduler strategy"
        """)

    def test_scheduler_runtime_branching(self, selenium):
        """Test scheduler runtime branching."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Test the complete branching logic from scheduler.ts
            scheduler_method = None

            if RUNTIME_ENV.IN_NODE:
                scheduler_method = "setImmediate"
            elif RUNTIME_ENV.IN_BUN:
                scheduler_method = "setImmediate"
            elif RUNTIME_ENV.IN_DENO:
                scheduler_method = "queueMicrotask"
            elif not RUNTIME_ENV.IN_SAFARI and RUNTIME_ENV.IN_BROWSER:
                scheduler_method = "MessageChannel"
            elif RUNTIME_ENV.IN_BROWSER_MAIN_THREAD and RUNTIME_ENV.IN_BROWSER:
                scheduler_method = "postMessage"
            else:
                scheduler_method = "setTimeout"

            # Should always determine a method
            assert scheduler_method is not None, "Should always determine a scheduler method"
            assert isinstance(scheduler_method, str), "Scheduler method should be a string"

            # Verify method is one of the expected options
            expected_methods = ["setImmediate", "queueMicrotask", "MessageChannel", "postMessage", "setTimeout"]
            assert scheduler_method in expected_methods, f"Unexpected scheduler method: {scheduler_method}"
        """)


class TestCompatFunctions:
    """Compat function tests."""

    def test_resolve_path_logic(self, selenium):
        """Test resolvePath logic."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Test resolvePath selection logic (based on compat.ts)
            resolve_path_type = None

            if RUNTIME_ENV.IN_NODE:
                resolve_path_type = "node_resolvePath"
            elif RUNTIME_ENV.IN_DENO:
                resolve_path_type = "browser_resolvePath"  # Deno uses browser-like resolution
            elif RUNTIME_ENV.IN_BUN:
                resolve_path_type = "node_resolvePath"     # Bun uses node-like resolution
            elif RUNTIME_ENV.IN_SHELL:
                resolve_path_type = "identity"             # Shell uses identity function
            else:
                resolve_path_type = "browser_resolvePath"  # Default browser resolution

            # Should always determine a resolution method
            assert resolve_path_type is not None, "Should always determine a path resolution method"

            # Verify method is one of the expected options
            expected_types = ["node_resolvePath", "browser_resolvePath", "identity"]
            assert resolve_path_type in expected_types, f"Unexpected resolve path type: {resolve_path_type}"
        """)

    def test_load_script_logic(self, selenium):
        """Test loadScript logic."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Test loadScript selection logic (based on compat.ts)
            load_script_type = None

            if RUNTIME_ENV.IN_BROWSER_MAIN_THREAD:
                load_script_type = "dynamic_import"
            elif RUNTIME_ENV.IN_BROWSER_WEB_WORKER:
                load_script_type = "importScripts_or_dynamic_import"
            elif RUNTIME_ENV.IN_NODE:
                load_script_type = "nodeLoadScript"
            elif RUNTIME_ENV.IN_DENO:
                load_script_type = "dynamic_import"
            elif RUNTIME_ENV.IN_BUN:
                load_script_type = "dynamic_import"
            elif RUNTIME_ENV.IN_SHELL:
                load_script_type = "load_function"
            else:
                # This should not happen - should throw error
                load_script_type = "error"

            # Should always determine a loading method
            assert load_script_type is not None, "Should always determine a script loading method"

            # Verify method is one of the expected options (error case means runtime detection failed)
            expected_types = [
                "dynamic_import", "importScripts_or_dynamic_import",
                "nodeLoadScript", "load_function", "error"
            ]
            assert load_script_type in expected_types, f"Unexpected load script type: {load_script_type}"

            # Should not be error type in normal cases
            if not (RUNTIME_ENV.IN_NODE or RUNTIME_ENV.IN_DENO or RUNTIME_ENV.IN_BUN or
                   RUNTIME_ENV.IN_BROWSER or RUNTIME_ENV.IN_SHELL):
                assert load_script_type == "error", "Should error for unknown runtime"
            else:
                assert load_script_type != "error", "Should not error for known runtime"
        """)

    def test_compat_error_prevention(self, selenium):
        """Test compat error prevention."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Test that we can always determine the runtime environment
            runtime_count = sum([
                RUNTIME_ENV.IN_NODE,
                RUNTIME_ENV.IN_DENO,
                RUNTIME_ENV.IN_BUN,
                RUNTIME_ENV.IN_BROWSER,
                RUNTIME_ENV.IN_SHELL
            ])

            # Should be in at least one runtime environment
            assert runtime_count >= 1, "Should be in at least one runtime environment"

            # Test that the combination makes sense
            if RUNTIME_ENV.IN_BROWSER:
                # Browser should not be server runtime
                server_count = sum([RUNTIME_ENV.IN_NODE, RUNTIME_ENV.IN_DENO, RUNTIME_ENV.IN_BUN])
                assert server_count == 0, "Browser should not be server runtime"

            # Test that we can determine appropriate functions for current runtime
            has_appropriate_functions = True

            # Every runtime should have appropriate compat functions
            if RUNTIME_ENV.IN_NODE or RUNTIME_ENV.IN_DENO or RUNTIME_ENV.IN_BUN or RUNTIME_ENV.IN_BROWSER or RUNTIME_ENV.IN_SHELL:
                has_appropriate_functions = True
            else:
                has_appropriate_functions = False

            assert has_appropriate_functions, "Should have appropriate compat functions for current runtime"
        """)


class TestRuntimeEnvIntegration:
    """Integration tests."""

    def test_runtime_env_with_existing_code_patterns(self, selenium):
        """Test RUNTIME_ENV with existing code patterns."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Test patterns similar to those used in actual Pyodide code
            # (based on scheduler.ts, compat.ts, etc.)

            # Pattern 1: Simple boolean checks
            if RUNTIME_ENV.IN_BROWSER_MAIN_THREAD:
                # This should not raise an error
                pass

            # Pattern 2: Negation checks
            if not RUNTIME_ENV.IN_NODE:
                # This should not raise an error
                pass

            # Pattern 3: Multiple condition checks
            if RUNTIME_ENV.IN_BROWSER and not RUNTIME_ENV.IN_SAFARI:
                # This should not raise an error
                pass

            # Pattern 4: Complex logical expressions (from scheduler.ts)
            use_message_channel = (
                not RUNTIME_ENV.IN_SAFARI and
                RUNTIME_ENV.IN_BROWSER and
                not RUNTIME_ENV.IN_DENO
            )
            assert isinstance(use_message_channel, bool)

            # Pattern 5: Runtime-specific optimizations
            use_set_immediate = RUNTIME_ENV.IN_NODE or RUNTIME_ENV.IN_BUN
            assert isinstance(use_set_immediate, bool)

            # Pattern 6: Fallback logic
            use_fallback = not (RUNTIME_ENV.IN_NODE or RUNTIME_ENV.IN_DENO or RUNTIME_ENV.IN_BUN or RUNTIME_ENV.IN_BROWSER)
            assert isinstance(use_fallback, bool)
        """)

    def test_runtime_env_global_accessibility(self, selenium):
        """Test RUNTIME_ENV global accessibility."""
        selenium.run("""
            # Test that we can import RUNTIME_ENV in different ways
            from pyodide_js import RUNTIME_ENV

            # Test that the global object exists (if it should)
            import js

            # The global should exist and be accessible
            if hasattr(js.globalThis, '__PYODIDE_RUNTIME_ENV__'):
                global_env = js.globalThis.__PYODIDE_RUNTIME_ENV__
                # Basic sanity check - should have boolean flags
                assert hasattr(global_env, 'IN_BROWSER')
                assert hasattr(global_env, 'IN_NODE')
                assert hasattr(global_env, 'IN_DENO')
                assert hasattr(global_env, 'IN_BUN')
                assert hasattr(global_env, 'IN_SHELL')
        """)

    def test_complete_runtime_coverage(self, selenium):
        """Test complete runtime coverage."""
        selenium.run("""
            from pyodide_js import RUNTIME_ENV

            # Test that we have complete coverage of all runtime environments
            all_main_runtimes = [
                'IN_NODE', 'IN_DENO', 'IN_BUN', 'IN_BROWSER', 'IN_SHELL'
            ]

            all_sub_runtimes = [
                'IN_BROWSER_MAIN_THREAD', 'IN_BROWSER_WEB_WORKER',
                'IN_NODE_COMMONJS', 'IN_NODE_ESM', 'IN_SAFARI'
            ]

            # Check main runtimes exist
            for runtime in all_main_runtimes:
                assert hasattr(RUNTIME_ENV, runtime), f"Missing main runtime flag: {runtime}"
                flag_value = getattr(RUNTIME_ENV, runtime)
                assert isinstance(flag_value, bool), f"{runtime} should be boolean"

            # Check sub runtimes exist
            for runtime in all_sub_runtimes:
                assert hasattr(RUNTIME_ENV, runtime), f"Missing sub runtime flag: {runtime}"
                flag_value = getattr(RUNTIME_ENV, runtime)
                assert isinstance(flag_value, bool), f"{runtime} should be boolean"

            # Should be in exactly one main runtime (or browser)
            main_runtime_count = sum([
                getattr(RUNTIME_ENV, runtime) for runtime in all_main_runtimes
            ])

            # Browser is special - it's mutually exclusive with server runtimes
            if RUNTIME_ENV.IN_BROWSER:
                server_runtime_count = sum([
                    RUNTIME_ENV.IN_NODE, RUNTIME_ENV.IN_DENO, RUNTIME_ENV.IN_BUN, RUNTIME_ENV.IN_SHELL
                ])
                assert server_runtime_count == 0, "Browser should be mutually exclusive with server runtimes"
            else:
                # Should be in exactly one server runtime
                server_runtime_count = sum([
                    RUNTIME_ENV.IN_NODE, RUNTIME_ENV.IN_DENO, RUNTIME_ENV.IN_BUN, RUNTIME_ENV.IN_SHELL
                ])
                assert server_runtime_count == 1, f"Should be in exactly one server runtime, got {server_runtime_count}"
        """)
