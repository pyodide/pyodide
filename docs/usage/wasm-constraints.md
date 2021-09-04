# Pyodide Python compatibility

## Python Standard library

Most of the Python standard library is functional, except for the modules
listed in the sections below. A large part of the CPython test suite passes except for
tests skipped in
[`src/tests/python_tests.txt`](https://github.com/pyodide/pyodide/blob/main/src/tests/python_tests.txt)
or via [patches](https://github.com/pyodide/pyodide/tree/main/cpython/patches).

### Optional modules

The following stdlib modules are included by default, however
they can be excluded with `loadPyodide({..., fullStdLib = false })`.
Individual modules can then be loaded as necessary using
{any}`pyodide.loadPackage`,

- distutils
- test: it is an exception to the above, since it is excluded by default.

### Removed modules

The following modules are removed from the standard library to reduce download size and
since they currently wouldn't work in the WebAssembly VM,

- curses
- dbm
- ensurepip
- idlelib
- lib2to3
- tkinter
- turtle.py
- turtledemo
- venv

### Included but not working modules

The following modules can be imported, but are not functional due to the limitations of the WebAssembly VM:

- multiprocessing
- threading
- sockets

as well as any functionality that requires these.
