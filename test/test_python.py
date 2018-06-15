import os
import pathlib
import time

from selenium.common.exceptions import JavascriptException


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


def test_python2js(selenium):
    assert selenium.run_js('return pyodide.runPython("None") === undefined')
    assert selenium.run_js('return pyodide.runPython("True") === true')
    assert selenium.run_js('return pyodide.runPython("False") === false')
    assert selenium.run_js('return pyodide.runPython("42") === 42')
    assert selenium.run_js('return pyodide.runPython("3.14") === 3.14')
    assert selenium.run_js(
        'return pyodide.runPython("\'碘化物\'") === "碘化物"')
    assert selenium.run_js(
        'let x = pyodide.runPython("b\'bytes\'");\n'
        'return (x instanceof window.Uint8ClampedArray) && '
        '(x.length === 5) && '
        '(x[0] === 98)')
    assert selenium.run_js(
        'let x = pyodide.runPython("[1, 2, 3]");\n'
        'return (x instanceof window.Array) && (x.length === 3) && '
        '(x[0] == 1) && (x[1] == 2) && (x[2] == 3)')
    assert selenium.run_js(
        'let x = pyodide.runPython("{42: 64}");\n'
        'return (typeof x === "object") && '
        '(x[42] === 64)')
    assert selenium.run_js(
        'let x = pyodide.runPython("open(\'/foo.txt\', \'wb\')")\n'
        'return (x.tell() === 0)\n')


def test_pythonexc2js(selenium):
    try:
        selenium.run_js('return pyodide.runPython("5 / 0")')
    except JavascriptException as e:
        assert('ZeroDivisionError' in str(e))


def test_js2python(selenium):
    selenium.run_js(
        'window.jsstring = "碘化物";\n'
        'window.jsnumber0 = 42;\n'
        'window.jsnumber1 = 42.5;\n'
        'window.jsundefined = undefined;\n'
        'window.jsnull = null;\n'
        'window.jstrue = true;\n'
        'window.jsfalse = false;\n'
        'window.jspython = pyodide.pyimport("open");\n'
        'window.jsbytes = new Uint8Array([1, 2, 3]);\n'
        'window.jsobject = new XMLHttpRequest();\n'
    )
    assert selenium.run(
        'from js import jsstring\n'
        'jsstring == "碘化物"')
    assert selenium.run(
        'from js import jsnumber0\n'
        'jsnumber0 == 42')
    assert selenium.run(
        'from js import jsnumber1\n'
        'jsnumber1 == 42.5')
    assert selenium.run(
        'from js import jsundefined\n'
        'jsundefined is None')
    assert selenium.run(
        'from js import jstrue\n'
        'jstrue is True')
    assert selenium.run(
        'from js import jsfalse\n'
        'jsfalse is False')
    assert selenium.run(
        'from js import jspython\n'
        'jspython is open')
    assert selenium.run(
        'from js import jsbytes\n'
        'jsbytes == b"\x01\x02\x03"')
    assert selenium.run(
        'from js import jsobject\n'
        'str(jsobject) == "[object XMLHttpRequest]"')


def test_import_js(selenium):
    result = selenium.run(
        "from js import window\nwindow.title = 'Foo'\nwindow.title")
    assert result == 'Foo'


def test_pyproxy(selenium):
    selenium.run(
        "class Foo:\n"
        "  bar = 42\n"
        "  def get_value(self, value):\n"
        "    return value * 64\n"
        "f = Foo()\n"
    )
    assert selenium.run_js("return pyodide.pyimport('f').get_value(2)") == 128
    assert selenium.run_js("return pyodide.pyimport('f').bar") == 42
    assert selenium.run_js("return ('bar' in pyodide.pyimport('f'))")
    selenium.run_js("f = pyodide.pyimport('f'); f.baz = 32")
    assert selenium.run("f.baz") == 32
    assert set(selenium.run_js(
        "return Object.getOwnPropertyNames(pyodide.pyimport('f'))")) == set(
            ['__class__', '__delattr__', '__dict__', '__dir__',
             '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__',
             '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__',
             '__lt__', '__module__', '__ne__', '__new__', '__reduce__',
             '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__',
             '__str__', '__subclasshook__', '__weakref__', 'bar', 'baz',
             'get_value', 'toString', 'prototype'])
    assert selenium.run("hasattr(f, 'baz')")
    selenium.run_js("delete pyodide.pyimport('f').baz")
    assert not selenium.run("hasattr(f, 'baz')")
    assert selenium.run_js(
        "return pyodide.pyimport('f').toString()").startswith('<Foo')


def test_jsproxy(selenium):
    assert selenium.run(
        "from js import document\n"
        "el = document.createElement('div')\n"
        "document.body.appendChild(el)\n"
        "document.body.children.length\n"
        ) == 1
    assert selenium.run(
        "document.body.children[0].tagName") == 'DIV'
    assert selenium.run(
        "repr(document)") == '[object HTMLDocument]'
    selenium.run_js(
        "window.square = function (x) { return x*x; }")
    assert selenium.run(
        "from js import square\n"
        "square(2)") == 4
    assert selenium.run(
        "from js import ImageData\n"
        "ImageData.new(64, 64)")


def test_open_url(selenium):
    assert selenium.run(
        "import pyodide\n"
        "pyodide.open_url('../test/data.txt').read()\n") == 'HELLO\n'


def test_run_core_python_test(python_test, selenium):
    selenium.load_package('test')
    try:
        selenium.run(
            "from test.libregrtest import main\n"
            "main(['{}'], verbose=True, verbose3=True)".format(python_test))
    except JavascriptException as e:
        assert str(e).strip().endswith('SystemExit: 0')


def pytest_generate_tests(metafunc):
    if 'python_test' in metafunc.fixturenames:
        test_modules = []
        with open(
                str(pathlib.Path(__file__).parents[0] /
                    "python_tests.txt")) as fp:
            for line in fp:
                line = line.strip()
                if line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) == 1:
                    test_modules.append(parts[0])
                    # XXX: The tests take too long to run, so we're just doing
                    # a sanity check on the first 25
                    if 'TRAVIS' in os.environ and len(test_modules) > 25:
                        break
        metafunc.parametrize("python_test", test_modules)
