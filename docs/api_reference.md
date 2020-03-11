# API Reference

*pyodide version 0.1.0*

Backward compatibility of the API is not guaranteed at this point.


## Python API


### pyodide.open_url(url)

Fetches a given *url* and returns a `io.StringIO` to access its contents.

*Parameters*

| name  | type | description     |
|-------|------|-----------------|
| *url* | str  | the URL to open |


*Returns*

A `io.StringIO` object with the URL contents./

### pyodide.eval_code(code, ns)

Runs a string of code. The last part of the string may be an expression, in which case, its value is returned.

This function may be overridden to change how `pyodide.runPython` interprets code, for example to perform
some preprocessing on the Python code first.

*Parameters*

| name   | type  | description           |
|--------|-------|-----------------------|
| *code* | str   | the code to evaluate  |
| *ns*   | dict  | evaluation name space |


*Returns*

Either the resulting object or `None`.

### pyodide.as_nested_list(obj)

Converts Javascript nested arrays to Python nested lists. This conversion can not
be performed automatically, because Javascript Arrays and Objects can be combined
in ways that are ambiguous.

*Parameters*

| name   | type  | description           |
|--------|-------|-----------------------|
| *obj*  | JS Object | The object to convert |

*Returns*

The object as nested Python lists.

## Javascript API

### pyodide.loadPackage(names, messageCallback, errorCallback)

Load a package or a list of packages over the network.

This makes the files for the package available in the virtual filesystem.
The package needs to be imported from Python before it can be used.

*Parameters*

| name              | type            | description                           |
|-------------------|-----------------|---------------------------------------|
| *names*           | {String, Array} | package name, or URL. Can be either a single element, or an array.          |
| *messageCallback* | function        | A callback, called with progress messages. (optional) |
| *errorCallback*   | function        | A callback, called with error/warning messages. (optional) |

*Returns*

Loading is asynchronous, therefore, this returns a `Promise`.


### pyodide.loadedPackages

`Object` with loaded packages.

Use `Object.keys(pyodide.loadedPackages)` to access the names of the
loaded packages, and `pyodide.loadedPackages[package_name]` to access
install location for a particular `package_name`.

### pyodide.pyimport(name)

Access a Python object from Javascript.  The object must be in the global Python namespace.

For example, to access the `foo` Python object from Javascript:

   `var foo = pyodide.pyimport('foo')`

*Parameters*

| name    | type   | description          |
|---------|--------|----------------------|
| *names* | String | Python variable name |


*Returns*

| name      | type    | description                           |
|-----------|---------|---------------------------------------|
| *object*  | *any*   | If one of the basic types (string,    |
|           |         | number, boolean, array, object), the  |
|           |         | Python object is converted to         |
|           |         | Javascript and returned.  For other   |
|           |         | types, a Proxy object to the Python   |
|           |         | object is returned.                   |

### pyodide.globals

An object whose attributes are members of the Python global namespace. This is a
more convenient alternative to `pyodide.pyimport`.

For example, to access the `foo` Python object from Javascript:

   `pyodide.globals.foo`

### pyodide.repr(obj)

Gets the Python's string representation of an object.

This is equivalent to calling `repr(obj)` in Python.

*Parameters*

| name    | type   | description         |
|---------|--------|---------------------|
| *obj*   | *any*  | Input object        |


*Returns*

| name       | type    | description                               |
|------------|---------|-------------------------------------------|
| *str_repr* | String  | String representation of the input object |


### pyodide.runPython(code)

Runs a string of code. The last part of the string may be an expression, in which case, its value is returned.

*Parameters*

| name    | type   | description                    |
|---------|--------|--------------------------------|
| *code*  | String | Python code to evaluate        |


*Returns*

| name       | type    | description                     |
|------------|---------|---------------------------------|
| *jsresult* | *any*   | Result, converted to Javascript |


### pyodide.runPythonAsync(code, messageCallback, errorCallback)

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


### pyodide.version()

Returns the pyodide version.

It can be either the exact release version (e.g. `0.1.0`), or
the latest release version followed by the number of commits since, and
the git hash of the current commit (e.g. `0.1.0-1-bd84646`).

*Parameters*

None

*Returns*

| name      | type   | description            |
|-----------|--------|------------------------|
| *version* | String | Pyodide version string |
