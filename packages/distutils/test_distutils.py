from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "distutils"], pytest_assert_rewrites=False)
def test_distutils(selenium):
    import sys
    import unittest
    import unittest.mock
    from test.libregrtest.main import main

    name = "test_distutils"

    ignore_tests = [
        "test_check_environ_getpwuid",  # no pwd
        "test_get_platform",  # no _osx_support
        "test_simple_built",
        "test_optional_extension",  # thread
        "test_customize_compiler_before_get_config_vars",  # subprocess
        "test_spawn",  # subprocess
        "test_debug_mode",  # no _osx_support
        "test_record",  # no _osx_support
        "test_get_config_h_filename",  # /include/python3.10/pyconfig.h not exists
        "test_srcdir",  # /lib/python3.10/config-3.10-wasm32-emscripten not exists
        "test_mkpath_with_custom_mode",
        "test_finalize_options",  # no executable
    ]
    match_tests = [[pat, False] for pat in ignore_tests]

    sys.modules["_osx_support"] = unittest.mock.Mock()
    try:
        main([name], match_tests=match_tests, verbose=True, verbose3=True)
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(f"Failed with code: {e.code}") from None
