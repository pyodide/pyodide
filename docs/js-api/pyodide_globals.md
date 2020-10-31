(js_api_pyodide_globals)=
# pyodide.globals

An alias to the global Python namespace.

An object whose attributes are members of the Python global namespace. This is a
more convenient alternative to {ref}`pyodide.pyimport <js_api_pyodide_pyimport>`.

For example, to access the `foo` Python object from Javascript:

```javascript
pyodide.globals.foo
```
