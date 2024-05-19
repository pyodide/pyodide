# Generating a custom lock file

For applications that have static dependencies that are not part of the Pyodide
lock file, the best way to load them is via a custom lock file. You can create a
Pyodide virtual environment with `pyodide-build` and then pip install either
from a direct url or from pypi. Then use `micropip.freeze()` to write out the
lock file. For example:

```sh
pip install pyodide-build
pyodide venv .venv-pyodide
.venv-pyodide/bin/pip install fastapi
.venv-pyodide/bin/python -c 'import micropip; print(micropip.freeze(), file=open("pyodide-lock.json","w"))'
```
Then serve the lock file and pass the url as the `lockFileURL` argument to `loadPyodide`:
```js
const pyodide = await loadPyodide({ lockFileURL : "https://wherever.com/you/served/it/pyodide-lock.json" });
// ...
```

