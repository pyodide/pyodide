# Projet roadmap

This document list general directions that core developers are interested to
see developed in Pyodide. The fact that an item is listed here is in no way a
promise that it will happen, as resources are limited. Rather, it is an
indication that help is welcomed on this topic.

## Reducing download sizes and initialization times

At present a first load of Pyodide requires to download 6.4 MB, and the
environment initialization takes 4 to 5 seconds. Subsequent page loads are faster
since assets are cached in the browser. Both of these indicators can likely be
improved, by optimizing compilation parameters, minifying the Python standard
library and packages, as well as a better profiling effort for the load
process.

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

## Simplification of package loading system


## Update SciPy to a more recent version

SciPy is a cornerstone of scientific computing in Python. It's a challenging
package to build for WebAssembly because it is large, includes Fortran code and
requires BLAS and LAPACK libraries. Currently Pyodide inclides scipy 0.17.1 from 2016,
and updating it is a blocker for using more recent versions of packages such as
scikit-learn, scikit-image, statsmodels, and MNE.


## Better project sustainability

for instance, by seeking synergies with the conda-forge project and its tooling.

# Better support for WebWorkers

# Better support for synchronous IO
