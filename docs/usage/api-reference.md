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
```


## Javascript API

Backward compatibility of the API is not guaranteed at this point.

| | |
|-|-|
| **{ref}`js_api_pyodide_globals`**        | An alias to the global Python namespace                        |
| **{ref}`js_api_pyodide_pyodide_py`**     | An alias to the pyodide Python package                         |
| **{ref}`pyodide.loadPackage(names, ...) <js_api_pyodide_loadPackage>`**    | Load a package or a list of packages over the network          |
| **{ref}`pyodide.loadPackageFromImports(code) <js_api_pyodide_loadPackagesFromImports>`**    | Inspect a Python code chunk and use ``pyodide.loadPackage` to load any known packages that the code chunk imports. |
| **{ref}`js_api_pyodide_loadedPackages`** | `Object` with loaded packages.                                 |
| **{ref}`pyodide.registerJsModule(name, js_object) <js_api_pyodide_registerJsModule>`**   | Registers a javascript object as a Python module.        |
| **{ref}`pyodide.unregisterJsModule(name) <js_api_pyodide_unregisterJsModule>`** | Unregisters a module previously registered with `js_api_pyodide_registerJsPackage`.        |
| **{ref}`js_api_pyodide_pyimport`**       | Access a Python object in the global namespace from Javascript |
| **{ref}`js_api_pyodide_runPython`**      | Runs Python code from Javascript.                              |
| **{ref}`pyodide.runPythonAsync(code, ...) <js_api_pyodide_runPythonAsync>`** | Runs Python code with automatic preloading of imports.         |
| **{ref}`js_api_pyodide_version`**        | The pyodide version string.                                    |
| **{ref}`pyodide.setInterruptBuffer(interruptBuffer) <js_api_pyodide_setInterruptBuffer>`** | Set the keyboard interrupt buffer                |


```{eval-rst}
.. toctree::
   :hidden:

   js-api/pyodide.globals.md
   js-api/pyodide.pyodide_py.md
   js-api/pyodide.loadPackage.md
   js-api/pyodide.loadPackagesFromImports.md
   js-api/pyodide.loadedPackages.md
   js-api/pyodide.registerJsModule.md
   js-api/pyodide.unregisterJsModule.md
   js-api/pyodide.pyimport.md
   js-api/pyodide.runPython.md
   js-api/pyodide.runPythonAsync.md
   js-api/pyodide.version.md
```


## Micropip API

```{eval-rst}
.. currentmodule:: micropip

.. autosummary::
   :toctree: ./micropip-api/

   micropip.install
```
