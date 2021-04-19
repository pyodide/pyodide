# Roadmap

This document list general directions that core developers are interested to
see developed in Pyodide. The fact that an item is listed here is in no way a
promise that it will happen, as resources are limited. Rather, it is an
indication that help is welcomed on this topic.

## Reducing download sizes and initialization times

At present a first load of Pyodide requires to download 6.4 MB, and the
environment initialization takes 4 to 5 seconds. Subsequent page loads are
faster since assets are cached in the browser. Both of these indicators can
likely be improved, by optimizing compilation parameters, minifying the Python
standard library and packages, reducing the number of exported symbols, as well
as a better profiling effort for the load process.

## Improve performance of Python code in Pyodide

Across [benchmarks](https://github.com/pyodide/pyodide/tree/main/benchmark)
Pyodide currently performs up to 3x to 5x slower than native Python.

At the same type, C code compiled to WebAssembly typically runs between near
native speed and 2x to 2.5x times slower (Jangda et al. 2019
[PDF](https://www.usenix.org/system/files/atc19-jangda.pdf)). It is therefore
very likely that the performance of Python code in Pyodide can be improved with
some focused effort.

In addition, scientific Python code would benefit from packaging a high
performance BLAS library such as BLIS.

## Simplification of the package loading system

Currently Pyodide has two way of loading packages:
 - `loadPackage` for packages built with Pyodide
 - and `micropip.install` for pure Python packages from PyPi
the user experience of combining these two tools can improved.

## Update SciPy to a more recent version

SciPy is a cornerstone of scientific computing in Python. It's a challenging
package to build for WebAssembly because it is large, includes Fortran code and
requires BLAS and LAPACK libraries. Currently Pyodide includes scipy 0.17.1 from 2016,
and updating it is a blocker for using more recent versions of packages such as
scikit-learn, scikit-image, statsmodels, and MNE.

## Better project sustainability

Some of the challenges that Pyodide faces, such as maintaining a collection of
build recipes, dependency resolution from PyPi, etc are already solved in
either Python or JavaScript ecosystems.  We should therefore strive to better
re-use existing tooling, and seeking synergies with existing initiatives in this
space, such as, conda-forge.

# Improve support for WebWorkers

WebWorkers are the main solution to run heavy computational tasks in a non
blocking manner in the browser. Currently Pyodide runs in WebWorkers,
however the user experience and reliability can be improved.

# Write http.client in terms of Web APIs

Python packages make an extensive use of packages such as `requests` to
synchronously fetch data. We currently can't use such packages since sockets
are not available in Pyodide. We could however try to re-implement some of the
stdlib libraries with Web APIs, potentially making this possible.
