(js_api_pyodide_loadPackagesFromImports)=
# pyodide.loadPackagesFromImports(code, messageCallback, errorCallback)

Inspect a Python code chunk and use ``pyodide.loadPackage` to load any known packages that the code chunk imports. Uses `pyodide_py.find_imports <pyodide.find\_imports>` to inspect the code.

For example, given the following code chunk

```python
import numpy as np
x = np.array([1, 2, 3])
```

`loadPackagesFromImports` will call `pyodide.loadPackage(['numpy'])`.
See also {ref}`js_api_pyodide_runPythonAsync`.


*Parameters*

| name              | type     | description                    |
|-------------------|----------|--------------------------------|
| *code*            | String   | code to inspect for packages to load. |
| *messageCallback* | function | A callback, called with progress messages. (optional) |
| *errorCallback*   | function | A callback, called with error/warning messages. (optional) |

*Returns*

| name       | type    | description                              |
|------------|---------|------------------------------------------|
| *result*   | Promise | Resolves to undefined on success. |
