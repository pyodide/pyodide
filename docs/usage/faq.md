# Frequently Asked Questions (FAQ)

## How can I load external python files in Pyodide?

The two possible solutions are,

- include these files in a python package, build a pure python wheel with
  `python setup.py bdist_wheel` and
  {ref}`load it with micropip <micropip-installing-from-arbitrary-urls>`.
- fetch the python code as a string and evaluate it in Python,
  ```js
  pyodide.runPython(await fetch('https://some_url/...'))
  ```

In both cases, files need to be served with a web server and cannot be loaded from local file system.

## Why can't I load files from the local file system?

For security reasons JavaScript in the browser is not allowed to load local data files. You need to serve them with a web-browser.
Recently there is a [Native File System API](https://wicg.github.io/file-system-access/) supported in Chrome but not in Firefox. [There is a discussion about implementing it for Firefox here.](https://github.com/mozilla/standards-positions/issues/154)


## How can I change the behavior of `runPython` and `runPythonAsync`?
The definitions of `runPython` and `runPythonAsync` are very simple:
```javascript
function runPython(code){
  pyodide.pyodide_py.eval_code(code, pyodide.globals);
}
```

```javascript
async function runPythonAsync(code, messageCallback, errorCallback) {
  await pyodide.loadPackagesFromImports(code, messageCallback, errorCallback);
  return pyodide.runPython(code);
};
```
To make your own version of `runPython`:

```javascript
pyodide.runPython(
  `
  import pyodide
  old_eval_code = pyodide.eval_code
  def my_eval_code(code, ns):
    extra_info = None
    result = old_eval_code(code, ns)
    return [ns["extra_info"], result]
  `
)

function myRunPython(code){
  return pyodide.globals.my_eval_code(code, pyodide.globals);
}

function myAsyncRunPython(code){
  await pyodide.loadPackagesFromImports(code, messageCallback, errorCallback);
  return pyodide.myRunPython(code, pyodide.globals);
}
```
Then `pyodide.myRunPython("2+7")` returns `[None, 9]` and
`pyodide.myRunPython("extra_info='hello' ; 2 + 2")` returns `['hello', 4]`.
If you want to change which packages `loadPackagesFromImports` loads, you can
monkey patch `pyodide-py.find_imports` which takes `code` as an argument
and returns a list of packages imported.

## How can I execute code in a custom namespace?
The second argument to `eval_code` is a namespace to execute the code in.
The namespace is a python dictionary. So you can use:
```javascript
pyodide.runPython(`
my_namespace = { "x" : 2, "y" : 7 }
def eval_in_my_namespace(code):
  return eval_code(code, my_namespace)
`);
pyodide.globals.eval_in_my_namespace("x")
```
which will return `2`.
<!-- TODO: change this when this is fixed! -->
Current deficiencies in the type conversions prevent the following code from working:
```
pyodide.pyodide_py.eval_code("x", pyodide.globals.ns)
```
raises `TypeError: globals must be a real dict`.


## How to detect that code is run with Pyodide?

**At run time**, you can detect that a code is running with Pyodide using,
```py
import sys

if "pyodide" in sys.modules:
   # running in Pyodide
```

More generally you can detect Python built with Emscripten (which includes
Pyodide) with,
```py
import platform

if platform.system() == 'Emscripten':
    # running in Pyodide or other Emscripten based build
```

This however will not work at build time (i.e. in a `setup.py`) due to the way
the pyodide build system works. It first compiles packages with the host compiler
(e.g. gcc) and then re-runs the compilation commands with emsdk. So the `setup.py` is
never run inside the Pyodide environement.

To detect pyodide, **at build time** use,
```python
import os

if "PYODIDE" in os.environ:
    # building for Pyodide
```
We used to use the environment variable `PYODIDE_BASE_URL` for this purpose,
but this usage is deprecated.


## How do I create custom python packages from javascript?

Put a collection of functions into a javascript object and use `pyodide.registerJsModule`:
Javascript:
```javascript
let my_module = {
  f : function(x){
    return x*x + 1;
  },
  g : function(x){
    console.log(`Calling g on argument ${x}`);
    return x;
  },
  submodule : {
    h : function(x) {
      return x*x - 1;
    },
    c  : 2,
  },  
};
pyodide.registerJsModule("my_js_module", my_module);
```
You can import your package like a normal Python package:
```
import my_js_module
from my_js_module.submodule import h, c
assert my_js_module.f(7) == 50
assert h(9) == 80
assert c == 2
```