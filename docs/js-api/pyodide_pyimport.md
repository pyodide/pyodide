(js_api_pyodide_pyimport)=
# pyodide.pyimport(name)

Access a Python object in the global namespace from Javascript.

For example, to access the `foo` Python object from Javascript:
```javascript
var foo = pyodide.pyimport('foo')
```

*Parameters*

| name    | type   | description          |
|---------|--------|----------------------|
| *names* | String | Python variable name |


*Returns*

| name      | type    | description                           |
|-----------|---------|---------------------------------------|
| *object*  | *any*   | If one of the basic types (string, number,<br>boolean, array, object), the Python<br> object is converted to        Javascript and <br>returned.  For other types, a Proxy<br> object to the Python object is returned. |
