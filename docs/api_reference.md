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
   pyodide.get_completions
   pyodide.open_url
   pyodide.JsException
```


## Javascript API

Backward compatibility of the API is not guaranteed at this point.

| | |
|-|-|
| **{ref}`js_api_pyodide_globals`**        | An alias to the global Python namespace                        |
| **{ref}`pyodide.loadPackage(names, ...) <js_api_pyodide_loadPackage>`**    | Load a package or a list of packages over the network          |
| **{ref}`js_api_pyodide_loadedPackages`** | `Object` with loaded packages.                                 |
| **{ref}`js_api_pyodide_pyimport`**       | Access a Python object in the global namespace from Javascript |
| **{ref}`js_api_pyodide_repr`**           | Gets the Python's string representation of an object.          |
| **{ref}`js_api_pyodide_runPython`**      | Runs Python code from Javascript.                              |
| **{ref}`pyodide.runPythonAsync(code, ...) <js_api_pyodide_runPythonAsync>`** | Runs Python code with automatic preloading of imports.         |
| **{ref}`js_api_pyodide_version`**        | Returns the pyodide version.                                   |


```{eval-rst}
.. toctree::
   :hidden:

   js-api/pyodide_globals.md
   js-api/pyodide_loadPackage.md
   js-api/pyodide_loadedPackages.md
   js-api/pyodide_pyimport.md
   js-api/pyodide_repr.md
   js-api/pyodide_runPython.md
   js-api/pyodide_runPythonAsync.md
   js-api/pyodide_version.md
```


## Micropip API

```{eval-rst}
.. currentmodule:: micropip

.. autosummary::
   :toctree: ./micropip-api/

   micropip.install
```
