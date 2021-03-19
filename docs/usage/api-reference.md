# API Reference

## Python API

Backward compatibility of the API is not guaranteed at this point.


```{eval-rst}
.. currentmodule:: pyodide

.. autosummary::
   :toctree: ./python-api/

   pyodide.as_nested_list
   pyodide.eval_code
   pyodide.find_imports
   pyodide.open_url
   pyodide.JsException
   pyodide.register_js_module
   pyodide.unregister_js_module
   pyodide.console.InteractiveConsole
   pyodide.console.repr_shorten
   pyodide.console.displayhook
   pyodide.webloop.WebLoop
   pyodide.create_proxy
   pyodide.create_once_callable
```


## Javascript API
Backward compatibility of the API is not guaranteed at this point.

```{eval-rst}
.. js:module:: pyodide
.. js:autofunction:: runPython
.. js:autofunction:: runPythonAsync
.. js:autoattribute:: globals
.. js:autoattribute:: pyodide_py
.. js:autoattribute:: version
.. js:autofunction:: pyimport
.. js:autofunction:: loadPackage
.. js:autoattribute:: loadedPackages
.. js:autofunction:: loadPackagesFromImports
.. js:autofunction:: registerJsModule
.. js:autofunction:: unregisterJsModule
```


## Micropip API

```{eval-rst}
.. currentmodule:: micropip

.. autosummary::
   :toctree: ./micropip-api/

   micropip.install
```
