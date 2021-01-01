(js_api_pyodide_loadPackagesFromImports)=
# pyodide.loadPackagesFromImports(code, messageCallback, errorCallback)

Inspect a Python code chunk and asynchronously load any known packages that the code
chunk imports.

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
