import os
from pathlib import Path
import time


import pytest


def test_init(selenium_standalone):
    assert 'Python initialization complete' in selenium_standalone.logs
    assert len(selenium_standalone.driver.window_handles) == 1


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
    # Need to test all three internal string representations in Python: UCS1,
    # UCS2 and UCS4
    assert selenium.run_js(
        'return pyodide.runPython("\'ascii\'") === "ascii"')
    assert selenium.run_js(
        'return pyodide.runPython("\'ιωδιούχο\'") === "ιωδιούχο"')
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
    except selenium.JavascriptException as e:
        assert('ZeroDivisionError' in str(e))
    else:
        assert False, 'Expected exception'


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
        'window.jsfloats = new Float32Array([1, 2, 3]);\n'
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
        '(jsbytes.tolist() == [1, 2, 3]) '
        'and (jsbytes.tobytes() == b"\x01\x02\x03")')
    assert selenium.run(
        'from js import jsfloats\n'
        'import struct\n'
        'expected = struct.pack("fff", 1, 2, 3)\n'
        '(jsfloats.tolist() == [1, 2, 3]) '
        'and (jsfloats.tobytes() == expected)')
    assert selenium.run(
        'from js import jsobject\n'
        'str(jsobject) == "[object XMLHttpRequest]"')


def test_typed_arrays(selenium):
    for wasm_heap in (False, True):
        for (jstype, pytype) in (
                ('Int8Array', 'b'),
                ('Uint8Array', 'B'),
                ('Uint8ClampedArray', 'B'),
                ('Int16Array', 'h'),
                ('Uint16Array', 'H'),
                ('Int32Array', 'i'),
                ('Uint32Array', 'I'),
                ('Float32Array', 'f'),
                ('Float64Array', 'd')):
            print(wasm_heap, jstype, pytype)
            if not wasm_heap:
                selenium.run_js(
                    f'window.array = new {jstype}([1, 2, 3, 4]);\n')
            else:
                selenium.run_js(
                    'var buffer = pyodide._malloc('
                    f'4 * {jstype}.BYTES_PER_ELEMENT);\n'
                    f'window.array = new {jstype}('
                    'pyodide.HEAPU8.buffer, buffer, 4);\n'
                    'window.array[0] = 1;\n'
                    'window.array[1] = 2;\n'
                    'window.array[2] = 3;\n'
                    'window.array[3] = 4;\n')
            assert selenium.run(
                'from js import array\n'
                'import struct\n'
                f'expected = struct.pack("{pytype*4}", 1, 2, 3, 4)\n'
                'print(array.format, array.tolist(), array.tobytes())\n'
                f'array.format == "{pytype}" '
                'and array.tolist() == [1, 2, 3, 4] '
                'and array.tobytes() == expected '
                f'and array.obj._has_bytes() is {not wasm_heap}')


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
             'get_value', 'toString', 'prototype', 'arguments', 'caller'])
    assert selenium.run("hasattr(f, 'baz')")
    selenium.run_js("delete pyodide.pyimport('f').baz")
    assert not selenium.run("hasattr(f, 'baz')")
    assert selenium.run_js(
        "return pyodide.pyimport('f').toString()").startswith('<Foo')


def test_pyproxy_destroy(selenium):
    selenium.run(
        "class Foo:\n"
        "  bar = 42\n"
        "  def get_value(self, value):\n"
        "    return value * 64\n"
        "f = Foo()\n"
    )
    try:
        selenium.run_js(
            "let f = pyodide.pyimport('f');\n"
            "console.assert(f.get_value(1) === 64);\n"
            "f.destroy();\n"
            "f.get_value();\n")
    except selenium.JavascriptException as e:
        assert 'Object has already been destroyed' in str(e)
    else:
        assert False, 'Expected exception'


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
    assert selenium.run(
        "from js import ImageData\n"
        "ImageData.typeof") == 'function'
    selenium.run_js(
        "class Point {\n"
        "  constructor(x, y) {\n"
        "    this.x = x;\n"
        "    this.y = y;\n"
        "  }\n"
        "}\n"
        "window.TEST = new Point(42, 43);")
    assert selenium.run(
        "from js import TEST\n"
        "del TEST.y\n"
        "TEST.y\n") is None
    selenium.run_js(
        "class Point {\n"
        "  constructor(x, y) {\n"
        "    this.x = x;\n"
        "    this.y = y;\n"
        "  }\n"
        "}\n"
        "window.TEST = new Point(42, 43);")
    assert selenium.run(
        "from js import TEST\n"
        "del TEST['y']\n"
        "TEST['y']\n") is None
    assert selenium.run(
        "from js import TEST\n"
        "TEST == TEST\n")
    assert selenium.run(
        "from js import TEST\n"
        "TEST != 'foo'\n")


def test_jsproxy_iter(selenium):
    selenium.run_js(
        "function makeIterator(array) {\n"
        "  var nextIndex = 0;\n"
        "  return {\n"
        "    next: function() {\n"
        "      return nextIndex < array.length ?\n"
        "        {value: array[nextIndex++], done: false} :\n"
        "        {done: true};\n"
        "    }\n"
        "  };\n"
        "}\n"
        "window.ITER = makeIterator([1, 2, 3]);")
    assert selenium.run(
        "from js import ITER\n"
        "list(ITER)") == [1, 2, 3]


def test_open_url(selenium):
    assert selenium.run(
        "import pyodide\n"
        "pyodide.open_url('test_data.txt').read()\n") == 'HELLO\n'


@pytest.mark.flaky(reruns=2)
def test_run_core_python_test(python_test, selenium, request):
    selenium.load_package('test')

    name, error_flags = python_test
    if error_flags:
        request.applymarker(pytest.mark.xfail(
            run=False, reason='known failure with code "{}"'
                              .format(error_flags)))
    try:
        selenium.run(
            "from test.libregrtest import main\n"
            "main(['{}'], verbose=True, verbose3=True)".format(name))
    except selenium.JavascriptException as e:
        assert 'SystemExit: 0' in str(e)


def pytest_generate_tests(metafunc):
    if 'python_test' in metafunc.fixturenames:
        test_modules = []
        test_modules_ids = []
        if 'CIRCLECI' not in os.environ or True:
            with open(
                    Path(__file__).parent / "python_tests.txt") as fp:
                for line in fp:
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue
                    error_flags = line.split()
                    name = error_flags.pop(0)
                    if (not error_flags
                        or set(error_flags).intersection(
                                {'crash', 'crash-chrome', 'crash-firefox'})):
                            test_modules.append((name, error_flags))
                            # explicitly define test ids to keep
                            # a human readable test name in pytest
                            test_modules_ids.append(name)
        metafunc.parametrize("python_test", test_modules,
                             ids=test_modules_ids)


def test_recursive_repr(selenium):
    assert not selenium.run(
        "d = {}\n"
        "d[42] = d.values()\n"
        "result = True\n"
        "try:\n"
        "   repr(d)\n"
        "except RecursionError:\n"
        "   result = False\n"
        "result")


def test_load_package_after_convert_string(selenium):
    """
    See #93.
    """
    selenium.run(
        "import sys\n"
        "x = sys.version")
    selenium.run_js(
        "var x = pyodide.pyimport('x')\n"
        "console.log(x)")
    selenium.load_package('kiwisolver')
    selenium.run(
        "import kiwisolver")
