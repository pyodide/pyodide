from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["test", "ssl"], pytest_assert_rewrites=False)
def test_ssl(selenium):
    import platform
    import unittest
    import unittest.mock

    from test.libregrtest.main import main

    platform.platform(aliased=True)
    name = "test_ssl"
    ignore_tests = [
        "*test_context_custom_class*",
        "*ThreadedTests*",
        "*ocket*",
        "test_verify_flags",
        "test_subclass",
        "test_lib_reason",
        "test_unwrap",
    ]
    match_tests = [[pat, False] for pat in ignore_tests]

    try:
        with unittest.mock.patch(
            "test.support.socket_helper.bind_port",
            side_effect=unittest.SkipTest("nope!"),
        ):
            main([name], match_tests=match_tests, verbose=True, verbose3=True)
    except SystemExit as e:
        if e.code != 0:
            raise RuntimeError(f"Failed with code: {e.code}") from None
