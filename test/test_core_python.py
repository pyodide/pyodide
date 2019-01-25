from pathlib import Path

import pytest


def test_cpython_core(python_test, selenium, request):

    name, error_flags = python_test

    # keep only flags related to the current browser
    flags_to_remove = ['firefox', 'chrome']
    flags_to_remove.remove(selenium.browser)
    for flag in flags_to_remove:
        if 'crash-' + flag in error_flags:
            error_flags.remove('crash-' + flag)

    if any(flag.startswith('segfault') for flag in error_flags):
        pytest.skip('known segfault with code: "{}"'
                    .format(','.join(error_flags)))

    if error_flags:
        if request.config.option.run_xfail:
            request.applymarker(pytest.mark.xfail(
                run=False, reason='known failure with code "{}"'
                                  .format(','.join(error_flags))))
        else:
            pytest.xfail('known failure with code "{}"'
                         .format(','.join(error_flags)))

    selenium.load_package('test')
    try:
        selenium.run(
            """
            from test.libregrtest import main
            try:
                main(['{}'], verbose=True, verbose3=True)
            except SystemExit as e:
                if e.code != 0:
                    raise RuntimeError(f'Failed with code: {{e.code}}')
            """.format(name))
    except selenium.JavascriptException:
        print(selenium.logs)
        raise


def pytest_generate_tests(metafunc):
    if 'python_test' in metafunc.fixturenames:
        test_modules = []
        test_modules_ids = []
        with open(
                Path(__file__).parent / "python_tests.txt") as fp:
            for line in fp:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                error_flags = line.split()
                name = error_flags.pop(0)
                test_modules.append((name, error_flags))
                # explicitly define test ids to keep
                # a human readable test name in pytest
                test_modules_ids.append(name)
        metafunc.parametrize("python_test", test_modules,
                             ids=test_modules_ids)
