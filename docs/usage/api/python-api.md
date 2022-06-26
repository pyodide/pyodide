# Python API

Backward compatibility of the API is not guaranteed at this point.

**JavaScript Modules**

By default there are two JavaScript modules. More can be added with
{any}`pyodide.registerJsModule`. You can import these modules using the Python
`import` statement in the normal way.

```{eval-rst}
.. list-table::

   *  - ``js``
      - The global JavaScript scope.
   *  - :js:mod:`pyodide_js <pyodide>`
      - The JavaScript Pyodide module.
```

**Python Modules**

```{eval-rst}
.. list-table::

   *  - :py:mod:`pyodide.code`
      - Utilities for evaluating Python and JavaScript code.
   *  - :py:mod:`pyodide.ffi`
      - The :any:`JsProxy` class and utilities to help interact with JavaScript code.
   *  - :py:mod:`pyodide.http`
      - Defines :any:`pyfetch` and other functions for making network requests.
```

```{eval-rst}
.. toctree::
   :hidden:

   python-api-code.md
   python-api-ffi.md
   python-api-http.md
```
