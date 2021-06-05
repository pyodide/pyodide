# py/pyodide and py/_pyodide

This directory consists of two Python packages py/_pyodide and py/pyodide. The
difference between these packages is when they are imported. They are both
imported by core/pyodide as a part of setting up the Pyodide/javascript foreign
function interface.

py/_pyodide is imported as the first step after initializing
the CPython interpreter. py/_pyodide cannot have any import time dependencies
other than the CPython stdlib.

py/pyodide is imported as the final step of core/pyodide. It has an import time
dependency on `_pyodide_core` which is a Python C extension assembled by
core/pyodide to serve the needs of py/pyodide.
