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

A `io.StringIO` object with the URL contents

### pyodide.eval_code(code, ns)

Runs a string of code, the last part of which may be an expression.

*Parameters*

| name   | type  | description           |
|--------|-------|-----------------------|
| *code* | str   | the code to evaluate  |
| *ns*   | dict  | evaluation name space |


*Returns*

Either the resulting object or `None`


## Javascript API

### pyodide.loadPackage(names)

Load a package or a list of packages


*Parameters*

| name    | type         | description                           |
|---------|--------------|---------------------------------------|
| *names* | {str, Array} | package name, or URL. Can be either a single element, or an array.          |


*Returns*

An evaluated promise.


### pyodide.loadedPackage

`Array` with loaded packages.

Use `Object.keys(pyodide.loadedPackage)` to access the names of the
loaded packages, and `pyodide.loadedPackage[package_name]` to access
install location for a particular `package_name`.

### pyodide.pyimport(name)

Import a Python package from Javascript.

Makes `var foo = pyodide.pyimport('foo')` work in Javascript.

*Parameters*

| name    | type  | description         |
|---------|-------|---------------------|
| *names* | str   | Python package name |


*Returns*

| name      | type    | description                           |
|-----------|---------|---------------------------------------|
| *package* | Object  | proxy for the imported Python package |


### pyodide.repr(obj)

Gets the string representation of an object

*Parameters*

| name    | type   | description         |
|---------|--------|---------------------|
| *obj*   | Object | Input object        |


*Returns*

| name       | type    | description                               |
|------------|---------|-------------------------------------------|
| *str_repr* | str     | String representation of the input object |


### pyodide.runPython(code)

Gets the string representation of an object

*Parameters*

| name    | type   | description                    |
|---------|--------|--------------------------------|
| *code*  | str    | Python code to evaluate        |


*Returns*

| name       | type    | description                    |
|------------|---------|--------------------------------|
| *jsresult* | Object  | Results, passed to Javascript  |


### pyodide.version()

Returns the pyodide version.

It can be either the exact release version (e.g. `0.1.0`), or 
the latest release version followed by the number of commits since, and
the git hash of the current commit (e.g. `0.1.0-1-bd84646`).

*Parameters*

None

*Returns*

| name      | type | description            |
|-----------|------|------------------------|
| *version* | str  | Pyodide version string |

