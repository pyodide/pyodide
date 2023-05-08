# Roadmap

This document lists general directions that core developers are interested to
see developed in Pyodide. The fact that an item is listed here is in no way a
promise that it will happen, as resources are limited. Rather, it is an
indication that help is welcomed on this topic.

## Improve documentation

Our API documentation is fairly detailed, but they need more introductory
information like tutorials. We also want to add more information to the FAQ and
improve the organization. It would also be good to find some way to include
interactive code pens in the documentation.

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

At the same time, C code compiled to WebAssembly typically runs between near
native speed and 2x to 2.5x times slower (Jangda et al. 2019
[PDF](https://www.usenix.org/system/files/atc19-jangda.pdf)). It is therefore
very likely that the performance of Python code in Pyodide can be improved with
some focused effort.

In addition, scientific Python code would benefit from packaging a high
performance BLAS library such as BLIS.

See issue {issue}`1120`.

## Find a better way to compile Fortran

Currently, we use f2c to cross compile Fortran to C. This does not work very
well because f2c only fully supports Fortran 77 code. LAPACK has used more
modern Fortran features since 2008 and Scipy has adopted more recent Fortran as
well. f2c still successfully generates code for all but 6 functions in Scipy +
LAPACK, but much of the generated code is slightly wrong and requires extensive
patching. There are still a large number of fatal errors due to call signature
incompatibilities.

If we could use an LLVM-based Fortran compiler as a part of the Emscripten
toolchain, most of these problems would be solved. There are several promising
projects heading in that direction including flang and lfortran.

See {issue}`scipy/scipy#15290`.

## Better project sustainability

Some of the challenges that Pyodide faces, such as maintaining a collection of
build recipes, dependency resolution from PyPI, etc are already solved in either
Python or JavaScript ecosystems. We should therefore strive to better re-use
existing tooling, and seeking synergies with existing initiatives in this space,
such as conda-forge.

See issue {issue}`795`.

## Improve support for WebWorkers

WebWorkers are necessary in order to run computational tasks in the browser
without hanging the user interface. Currently, Pyodide can run in a WebWorker,
however the user experience and reliability can be improved.

See issue {issue}`1504`.

## Synchronous IO

The majority of existing I/O APIs are synchronous. Unless we can support
synchronous IO, much of the existing Python ecosystem cannot be ported. There
are several different approaches to this, we would like to support at least one
method.

See issue {issue}`1503`.

(http-client-limit)=

## Write http.client in terms of Web APIs

Python packages make an extensive use of packages such as `requests` to
synchronously fetch data. We currently can't use such packages since sockets
are not available in Pyodide. We could however try to re-implement some
stdlib libraries with Web APIs, potentially making this possible.

Because http.client is a synchronous API, we first need support for synchronous
IO.

See issue {issue}`140`.
