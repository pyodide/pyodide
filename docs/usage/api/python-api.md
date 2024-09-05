(python-api)=

# Python API

Backward compatibility of the API is not guaranteed at this point.

**JavaScript Modules**

By default there are two JavaScript modules. More can be added with
{js:func}`pyodide.registerJsModule`. You can import these modules using the Python
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
   *  - :py:mod:`pyodide.console`
      - Similar to the builtin :py:mod:`code` module but handles top level await. Used
        for implementing the Pyodide console.
   *  - :py:mod:`pyodide.ffi`
      - The :py:class:`~pyodide.ffi.JsProxy` class and utilities to help interact with JavaScript code.
   *  - :py:mod:`pyodide.http`
      - Defines :py:func:`~pyodide.http.pyfetch` and other functions for making network requests.
   *  - :py:mod:`pyodide.webloop`
      - The Pyodide event loop implementation. This is automatically configured
        correctly for most use cases it is unlikely you will need it outside of niche
        use cases.
```

```{eval-rst}
.. toctree::
   :hidden:

   python-api/code.md
   python-api/console.md
   python-api/ffi.md
   python-api/http.md
   python-api/webloop.md
```
