(packages-in-pyodide)=

# Packages built in Pyodide

This is the list of Python packages included with the current version of
Pyodide. These packages can be loaded with {js:func}`pyodide.loadPackage` or
{py:func}`micropip.install`. See {ref}`loading_packages` for information about
loading packages. Pure Python packages with wheels on PyPI can be loaded
directly from PyPI with {py:func}`micropip.install`.

The table below is generated from the lockfile configured for this Pyodide
release. New package recipes merged in
[`pyodide-recipes`](https://github.com/pyodide/pyodide-recipes) may appear in a
later Pyodide release after the lockfile is updated.

If you want to try packages from the latest recipe builds before they appear in
this table, install from the Pyodide package indexes with
{py:func}`micropip.install` and the `index_urls` argument:

```py
import micropip

await micropip.install(
    "your-package-name",
    index_urls=[
        "https://pypi.anaconda.org/pyodide-nightly/simple",
        "https://pypi.org/simple",
    ],
)
```

```{eval-rst}
.. pyodide-package-list :: packages
```
