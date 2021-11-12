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

```{eval-rst}
.. currentmodule:: pyodide

.. automodule:: pyodide
   :members:
   :autosummary:
   :autosummary-no-nesting:
```
