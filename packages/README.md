# Pyodide packages

This folder contains the list of packages built in pyodide.

There are two categories of packages,
 1. Those that contain a `meta.yaml` are built with the Python build system
    using `pyodide_build/buildall.py` and `pyodide_build/buildpkg.py` scripts.
 2. Those that contain a `Makefile` are build from the main `Makefile` in the
    root folder.

Packages of the second category will be migrated to use a `meta.yaml` in the
future (see [#713](https://github.com/iodide-project/pyodide/issues/713)).
