# Building from sources

To install Pyodide from sources follow the steps in the
[readme](./rootdir.html#building-from-source).


## Partial builds

To build a subset of available packages in pyodide, set the environment
variable `PYODIDE_PACKAGES` to a comma separated list of packages. For
instance,

```
PYODIDE_PACKAGES="toolz,attrs" make
```

Note that this environment variable must contain both the packages and their
dependencies. The package names must match the folder names in `packages/`
exactly; in particular they are case sensitive.

To build a minimal version of pyodide, set `PYODIDE_PACKAGES="micropip"`. The
micropip and package is generally always included for any non empty value of
`PYODIDE_PACKAGES`.

If scipy is included in `PYODIDE_PACKAGES`, BLAS/LAPACK must be manually built
first with `make -c CLAPACK`.
