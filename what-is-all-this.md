The Pyodide runtime consists of the following components:

1. Emscripten
2. CPython
3. The py/_pyodide package which is a Python package with pure Python code
   avaiable in the inner stage of the Pyodide bootstrap process.
4. The core/pyodide code, implemented in a mix of C and Javascript, which embeds
   the CPython interpreter in an emscripten application. At initialization, this
   relies on on py/_pyodide.
   At runtime this relies on py/pyodide and js/pyodide. The final stage of
   initialization is to import py/pyodide.
5. The py/pyodide package which has Python code that is needed for the outer
   stage of the Pyodide bootstrap process. py/pyodide relies on core/pyodide at
   import time and relies on js/pyodide at runtime.
6. The js/pyodide package which defines the Javascript public API, sets up the
   process of loading the core/pyodide emscripten application + CPython
   interpreter, and then completes the bootstrap by injecting the js/pyodide
   API into the Python sys.modules.
7. The packages directory, which contains a large number of CPython packages
   built to run in Pyodide.

One of our long-term organizational goals is to carefully organize core/pyodide,
py/pyodide, and js/pyodide to clarify which functionality is not part of the
tangled web of runtime dependencies that define Pyodide's core behavior.
