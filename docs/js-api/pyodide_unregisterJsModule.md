(js_api_pyodide_unregisterJsModule)=
# pyodide.unregisterJsModule(name)

Unregisters a Js module with given name that has been previously registered with `js_api_pyodide_registerJsModule` or ``pyodide.register_js_module``. If a Js module with that name does not already exist, will throw an error. Note that if the module has already been imported, this won't have much effect unless you also delete the imported module from ``sys.modules``. This calls the ``pyodide_py`` api ``pyodide_py.unregister_js_module``.

**Parameters**

| name    | type   | description                    |
|---------|--------|--------------------------------|
| *name*  | String | Name of js module              |

