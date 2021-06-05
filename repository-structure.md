The Pyodide runtime consists of the following components, sorted in terms of
initialization-time (or import-time) dependencies.

1. CPython
2. The py/_pyodide package which is a Python package with pure Python code
   avaiable in the inner stage of the Pyodide bootstrap process.
3. The core/pyodide code, implemented in a mix of C and Javascript, which embeds
   the CPython interpreter in an emscripten application. This relies on
   py/pyodide and js/pyodide at runtime. The final stage of initialization is to
   import py/pyodide.
4. The py/pyodide package which has Python code that is needed for the outer
   stage of the Pyodide bootstrap process. py/pyodide relies on core/pyodide at
   import time and relies on js/pyodide at runtime.
5. The js/pyodide package which defines the Javascript public API, sets up the
   process of loading the core/pyodide emscripten application + CPython
   interpreter, and then completes the bootstrap by injecting the js/pyodide
   API into the Python `sys.modules`.
6. The packages directory, which contains a large number of CPython packages
   built to run in Pyodide.

One of our long-term organizational goals is to carefully organize core/pyodide,
py/_pyodide, py/pyodide, and js/pyodide to clarify which functionality is not part of
runtime dependencies that define Pyodide's core behavior.
