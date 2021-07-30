# Roadmap

This document lists general directions that core developers are interested to
see developed in Pyodide. The fact that an item is listed here is in no way a
promise that it will happen, as resources are limited. Rather, it is an
indication that help is welcomed on this topic.

## Reducing download sizes and initialization times

At present a first load of Pyodide requires a 6.4 MB download, and the
environment initialization takes 4 to 5 seconds. Subsequent page loads are
faster since assets are cached in the browser. Both of these indicators can
likely be improved, by optimizing compilation parameters, minifying the Python
standard library and packages, reducing the number of exported symbols. To
figure out where to devote the effort, we need a better profiling system for the
load process.

See issue {issue}`646`.

## Improve performance of Python code in Pyodide

Across [benchmarks](https://github.com/pyodide/pyodide/tree/main/benchmark)
Pyodide is currently around 3x to 5x slower than native Python.

At the same type, C code compiled to WebAssembly typically runs between near
native speed and 2x to 2.5x times slower (Jangda et al. 2019
[PDF](https://www.usenix.org/system/files/atc19-jangda.pdf)). It is therefore
very likely that the performance of Python code in Pyodide can be improved with
some focused effort.

In addition, scientific Python code would benefit from packaging a high
performance BLAS library such as BLIS.

See issue {issue}`1120`.

## Simplification of the package loading system

Currently Pyodide has two way of loading packages:

- `loadPackage` for packages built with Pyodide and
- `micropip.install` for pure Python packages from PyPi.

The relationship between these tools is confusing and could be simplified.
Furthermore, the dependency resolution logic and packaging / build system could
be improved.

See issues {issue}`1470` and {issue}`1100`.

## Update SciPy to a more recent version

SciPy is a cornerstone of scientific computing in Python. It's a challenging
package to build for WebAssembly because it is large, includes Fortran code, and
requires BLAS and LAPACK libraries. Currently Pyodide includes scipy 0.17.1 from 2016.
Updating it is a blocker for using more recent versions of packages such
as scikit-learn, scikit-image, statsmodels, and MNE.

See issue {issue}`549`.

## Better project sustainability

Some of the challenges that Pyodide faces, such as maintaining a collection of
build recipes, dependency resolution from PyPi, etc are already solved in either
Python or JavaScript ecosystems. We should therefore strive to better re-use
existing tooling, and seeking synergies with existing initiatives in this space,
such as conda-forge.

See issue {issue}`795`.

## Improve support for WebWorkers

WebWorkers are necessary in order to run computational tasks in the browser
without hanging the user interface. Currently Pyodide can run in a WebWorker,
however the user experience and reliability can be improved.

See issue {issue}`1504`.

## Synchronous IO

The majority of existing I/O APIs are synchronous. Unless we can support
synchronous IO, much of the existing Python ecosystem cannot be ported. Luckily
{user}`joemarshall` has a solution for this involving rewinding the Python
stack. He has [a prototype implementation
here](https://github.com/joemarshall/unthrow). We would like to bring this into
Pyodide as a core feature.

See issue {issue}`1503`.

## Write http.client in terms of Web APIs

Python packages make an extensive use of packages such as `requests` to
synchronously fetch data. We currently can't use such packages since sockets
are not available in Pyodide. We could however try to re-implement some of the
stdlib libraries with Web APIs, potentially making this possible.

Because http.client is a synchronous API, we first need support for synchronous
IO.

See issue {issue}`140`.
