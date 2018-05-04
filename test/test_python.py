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


def test_import_js(selenium):
    result = selenium.run(
        "from js import window\nwindow.title = 'Foo'\nwindow.title")
    assert result == 'Foo'


def test_py_proxy(selenium):
    selenium.run(
        "class Foo:\n  bar = 42\n  def get_value(self):\n    return 64\nf = Foo()\n")
    assert selenium.run_js("return pyodide.pyimport('f').get_value()") == 64
    assert selenium.run_js("return pyodide.pyimport('f').bar") == 42
    assert selenium.run_js("return ('bar' in pyodide.pyimport('f'))") == True
    selenium.run_js("f = pyodide.pyimport('f'); f.baz = 32")
    assert selenium.run("f.baz") == 32
    assert set(selenium.run_js(
        "return Object.getOwnPropertyNames(pyodide.pyimport('f'))")) == set(
            ['$$', '__class__', '__delattr__', '__dict__', '__dir__',
             '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__',
             '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__',
             '__lt__', '__module__', '__ne__', '__new__', '__reduce__',
             '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__',
             '__str__', '__subclasshook__', '__weakref__', 'bar', 'baz',
             'get_value'])
    assert selenium.run("hasattr(f, 'baz')") == True
    selenium.run_js("delete pyodide.pyimport('f').baz")
    assert selenium.run("hasattr(f, 'baz')") == False


def test_run_core_python_test(python_test, selenium):
    selenium.run(
        "import sys\n"
        "exitcode = -1\n"
        "def exit(n=0):\n"
        "    global exitcode\n"
        "    exitcode = n\n"
        "    raise SystemExit()\n\n"
        "sys.exit = exit\n")
    # Undo the lazy modules setup -- it interferes with the CPython test
    # harness
    selenium.run(
        "for k in list(sys.modules):\n"
        "    if k.startswith('numpy'):\n"
        "        del sys.modules[k]\n")
    selenium.run(
        "from test.libregrtest import main\n"
        "main(['{}'], verbose=True, verbose3=True)".format(python_test))
    exitcode = selenium.run("exitcode")
    assert exitcode == 0


def pytest_generate_tests(metafunc):
    if 'python_test' in metafunc.fixturenames:
        test_modules = []
        with open(
                str(pathlib.Path(__file__).parents[0] / "python_tests.txt")) as fp:
            for line in fp:
                line = line.strip()
                if line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) == 1:
                    test_modules.append(parts[0])
                    # XXX: The tests take too long to run, so we're just doing a
                    # sanity check on the first 25
                    if len(test_modules) > 25:
                        break
        metafunc.parametrize("python_test", test_modules)
