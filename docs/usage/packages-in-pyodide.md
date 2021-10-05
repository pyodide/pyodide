
(packages-in-pyodide)=
# Packages built in Pyodide

The list of prebuilt Python packages in the current version of Pyodide.
These packages can be loaded through {any}`pyodide.loadPackage` or {any}`micropip.install`.
See {ref}`loading_packages` for information about loading packages.
Note that in addition to this list, pure Python packages with wheels can be loaded
directly from PyPI with {any}`micropip.install`.

```{eval-rst}
.. pyodide-package-list :: packages
```