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

## Minimal build

Minimal pyodide build can be enabled by setting the `PYODIDE_MINIMAL`
environment variable.  For instance,
```
PYODIDE_MINIMAL=true PYODIDE_PACKAGES="micropip" make
```

This will,
 - not include freetype and libpng libraries (it won't be possible to build matplotlib)
 - not include the jedi library, disabling auto-completion in iodide

As as a result the size will of the core pyodide binaries will be ~15% smaller.
