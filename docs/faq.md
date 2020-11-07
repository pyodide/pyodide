# Frequently Asked Questions (FAQ)

## How can I load external python files in Pyodide?

The two possible solutions are,

- include these files in a python package, build a pure python wheel with
  `python setup.py bdist_wheel` and
  {ref}`load it with micropip <micropip-installing-from-arbitrary-urls>`.
- fetch the python code as a string and evaluate it in Python,
  ```js
  pyodide.eval_code(pyodide.open_url('https://some_url/...'))
  ```

In both cases, files need to be served with a web server and cannot be loaded from local file system.

## Why can't I load files from the local file system?

For security reasons JavaScript in the browser is not allowed to load local
data files. You need to serve them with a web-browser.

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

if "PYODIDE_PACKAGE_ABI" in os.environ:
    # building for Pyodide
```
