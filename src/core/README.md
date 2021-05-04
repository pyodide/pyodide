# core/pyodide

The C and Javascript code in this package is responsible for embedding the
Python interpreter in our emscripten js/wasm application. The primary purpose of
this code is to define the foreign function interface between Python and
Javascript. Once this foreign function interface is defined, more complex
behaviors are better defined in Python when possible for easier development and
debugging.

In particular, when possible logic should be moved from core/pyodide to
py/_pyodide or to py/pyodide.

The core/pyodide code is responsible for the following main steps:

1. Initialize the CPython interpreter
2. Import py/_pyodide
3. Initialize `_pyodide_core` which is a Python C extension that we use to make
   functionality available to py/pyodide.
4. Set up functionality to automatically convert functions from Javascript to
   CPython calling conventions (`error_handling.h`).
5. Set up the "hiwire" side table to hold references to Javascript objects --
   necessary because wasm variables can only hold numbers (`hiwire.c`).
6. Set up type conversions of basic types between Python and Javascript
   (`js2python.c` and `python2js.c`).
7. Set up Proxying of remaining types between Python and Javascript (`jsproxy.c`
   and `pyproxy.c`). This is the most complicated part of the Pyodide runtime
   and involves careful conversion between [abstract Javascript object
   protocols](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy)
   (see also [Javascript Iteration
   Protocols](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Iteration_protocols)
   )
   and [Python object protocols](https://docs.python.org/3/c-api/abstract.html).
8. Add `_pyodide_core` to `sys.modules` and import py/pyodide.
