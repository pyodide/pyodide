# Pyodide Python compatibility


## Python Standard library

Most of the Python standard library is functional, except for the modules
listed in the sections below. A large part of the CPython test suite passes except for
tests skipped in
[`src/tests/python_tests.txt`](https://github.com/pyodide/pyodide/blob/main/src/tests/python_tests.txt)
or via [patches](https://github.com/pyodide/pyodide/tree/main/cpython/patches).

### Removed modules

The following modules are removed from the standard library to reduce download size and
since they currently wouldn't work in the WebAssembly VM,

 - ctypes
 - curses
 - dbm
 - ensurepip
 - idlelib
 - lib2to3
 - tkinter
 - turtle.py
 - turtledemo
 - venv
 - webbrowser.py

### Included but not working modules

The following modules can be imported, but are not functional due to the limitations of the WebAssembly VM,
 - multiprocessing
 - threading
 - sockets

as well as any functionality that requires these.

### Unvendored modules

The following stdlib modules are not included by default, however they can be
loaded as an external package when necessary with {any}`pyodide.loadPackage`,

 - test
 - distutils
