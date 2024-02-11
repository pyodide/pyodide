# Pyodide Python compatibility

## Python Standard library

Most of the Python standard library is functional, except for the modules
listed in the sections below. A large part of the CPython test suite passes except for
tests skipped in
[`src/tests/python_tests.yaml`](https://github.com/pyodide/pyodide/blob/main/src/tests/python_tests.yaml)
or via [patches](https://github.com/pyodide/pyodide/tree/main/cpython/patches).

### Optional modules

The following stdlib modules are unvendored by default,
in order to reduce initial download size of Python distribution.
You can load all unvendored stdlib modules
when initializing Pyodide with, `loadPyodide({ fullStdLib : true })`.
However this has a significant impact on the download size.
Instead, it is better to load individual modules as needed using
{js:func}`pyodide.loadPackage` or {py:func}`micropip.install`.

- ssl
- lzma
- sqlite3
- test: it is an exception to the above, since it is not loaded even if `fullStdLib` is set to true.

#### Modules with limited functionality

- hashlib: Hash algorithms that are depending on OpenSSL are not available by default.
  See Python [hashlib documentation](https://docs.python.org/3/library/hashlib.html)
  for list of algorithms that are dependent on OpenSSL. If you need those algorithms,
  you need to call `pyodide.loadPackage('hashlib')` or `micropip.install('hashlib')`
  **before** importing hashlib.

- decimal: The decimal module has C (\_decimal) and Python (\_pydecimal) implementations
  with the same functionality. The Python implementation is not available by default.
  If you need a Python implementation of decimal, you need to call
  `pyodide.loadPackage('pydecimal')` or `micropip.install('pydecimal')`,
  then explicitly import `_pydecimal`.

- pydoc: Help messages for Python builtins are not available by default
  in order to reduce the initial download size. You need to call
  `pyodide.loadPackage('pydoc_data')` or `micropip.install('pydoc_data')`
  to enable them.

- webbrowser: The original webbrowser module is not available. Instead,
  Pyodide includes some method stubs based on browser APIs:
  `webbrowser.open()`, `webbrowser.open_new()`, `webbrowser.open_new_tab()`.

### Synchronous HTTP requests support

Packages for `urllib3` and `requests` are included in pyodide. In browser, these
function _roughly_ the same as on other operating systems with some
limitations. In node.js, they are currently untested, they will require
at least a polyfill for synchronous XMLHttpRequest, and WebWorker.

The first limitation is that streaming download of files only works
in very specific circumstances, which are that pyodide has to be running
in a web-worker, and it has to be on a cross-origin isolated website.
If either of these conditions are not met, it will do a non-streaming
request, i.e. download the full request body before it returns from the
initial request call.

Secondly, all network calls are done via the browser. This means you are
subject to the same limitations as any JavaScript network call. This means
you have very little or no control over certificates, timeouts, proxies and
other network related settings. You also are constrained by browser policies
relating to cross-origin requests, sometimes things will be blocked by CORS
policies if the server doesn't serve them with the correct headers.

### Removed modules

The following modules are removed from the standard library to reduce download size and
since they currently wouldn't work in the WebAssembly VM,

- curses
- dbm
- ensurepip
- fcntl
- grp
- idlelib
- lib2to3
- msvcrt
- pwd
- resource
- syslog
- termios
- tkinter
- turtle.py
- turtledemo
- venv
- winreg
- winsound

### Included but not working modules

The following modules can be imported, but are not functional due to the limitations of the WebAssembly VM:

- multiprocessing
- threading
- sockets

as well as any functionality that requires these.

The following are present but cannot be imported due to a dependency on the termios package which has been removed:

- pty
- tty
