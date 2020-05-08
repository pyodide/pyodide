# Building from sources

To install Pyodide from sources follow the steps in the
[readme](./rootdir.html#building-from-source).


## Partial builds

To build a subset of available packages in pyodide, set the environement
variable `PYODIDE_PACKAGES` to a comma separated list of packages. For
instance,

```
PYODIDE_PACKAGES="toolz,attrs" make
```

Note that this environement variables must contain both the packages and their
dependencies. The package names must much the folder names in `packages/`
exactly; in particular they are case sensitive.
