import pathlib
import time

import pytest


def test_init(selenium):
    assert 'Python initialization complete' in selenium.logs
    assert len(selenium.driver.window_handles) == 1


def test_webbrowser(selenium):
    selenium.run("import antigravity")
    time.sleep(2)
    assert len(selenium.driver.window_handles) == 2


def test_print(selenium):
    selenium.run("print('This should be logged')")
    assert 'This should be logged' in selenium.logs


@pytest.mark.skipif(True, reason="Experimental")
def test_run_core_python_test(python_test, selenium):
    selenium.run(
        "import sys\n"
        "sys.argv = ['pyodide']\n"
        "exitcode = -1\n"
        "def exit(n):\n"
        "    global exitcode\n"
        "    exitcode = n\n"
        "    raise SystemExit()\n\n"
        "sys.exit = exit\n")
    selenium.run(
        "from test.libregrtest import main\n"
        "main(['{}'], verbose=True, verbose3=True)".format(python_test))
    exitcode = selenium.run("exitcode")
    if exitcode != 0:
        print('\n'.join(selenium.logs))
    assert exitcode == 0


@pytest.mark.skipif(True, reason="Experimental")
def pytest_generate_tests(metafunc):
    if 'python_test' in metafunc.fixturenames:
        test_modules = []
        with open(
                pathlib.Path(__file__).parents[0] / "python_tests.txt") as fp:
            for line in fp:
                parts = line.strip().split()
                if len(parts) == 1:
                    test_modules.append(parts[0])
        metafunc.parametrize("python_test", test_modules)
