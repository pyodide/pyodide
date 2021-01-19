(js_api_pyodide_registerJsModule)=
# pyodide.registerJsModule(name, module)

Registers the Js object ``module`` as a Js module with ``name``. This module can then be imported from Python using the standard Python import system. If another module by the same name has already been imported, this won't have much effect unless you also delete the imported module from ``sys.modules``. This calls the ``pyodide_py`` api ``pyodide_py.register_js_module``.


**Parameters**

| name      | type   | description                          |
|-----------|--------|--------------------------------------|
| *name*    | String | Name of js module                    |
| *module*  | object | Javascript object backing the module |
