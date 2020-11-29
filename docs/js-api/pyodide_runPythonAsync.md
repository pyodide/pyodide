(js_api_pyodide_runPythonAsync)=
# pyodide.runPythonAsync(code, messageCallback, errorCallback)

Runs Python code, possibly asynchronously loading any known packages that the code
chunk imports.

For example, given the following code chunk

```python
import numpy as np
x = np.array([1, 2, 3])
```

pyodide will first call `pyodide.loadPackage(['numpy'])`, and then run the code
chunk, returning the result. Since package fetching must happen asynchronously,
this function returns a `Promise` which resolves to the output. For example, to
use:

```javascript
pyodide.runPythonAsync(code, messageCallback)
  .then((output) => handleOutput(output))
```

*Parameters*

| name              | type     | description                    |
|-------------------|----------|--------------------------------|
| *code*            | String   | Python code to evaluate        |
| *messageCallback* | function        | A callback, called with progress messages. (optional) |
| *errorCallback*   | function        | A callback, called with error/warning messages. (optional) |

*Returns*

| name       | type    | description                              |
|------------|---------|------------------------------------------|
| *result*   | Promise | Resolves to the result of the code chunk |
