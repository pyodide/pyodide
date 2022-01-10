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

## Better support and documentation for loading user Python code

Currently, most of our documentation suggests using `pyodide.runPython` to run
code. This makes code difficult to maintain, because it won't work with `mypy`,
`black`, or other code analysis tools, doesn't get good syntax highlighting in
editors, etc. It also may lead to passing "arguments" to code via string
formatting, missing out on the type conversion utilities.

Our goal is to develop and document a better workflow for users to develop
Python code for use in Pyodide.

See issue {issue}`1940`.

## Improvements to package loading system

Currently, Pyodide has two ways of loading packages:

- {any}`pyodide.loadPackage` for packages built with Pyodide and
- {any}`micropip.install` for pure Python packages from PyPI.

The relationship between these tools is currently confusing.

Our goal is to have three ways to load packages: one with no dependency
resolution at all, one with static dependency resolution which is done ahead of
time, and one for dynamic dependency resolution. Ideally most applications can
use static dependency resolution and repls can use dynamic dependency
resolution.

See issues {issue}`2045` and {issue}`1100`.

## Switch to using wheels for Python packages

We are planning to switch from using Emscripten's file packager to packaging
Python packages as wheels. Other shared libraries can be bundled as zip or tar
archives. This makes us more compliant with the general Python ecosystem and
makes the archive files easier to inspect. They could also be used more easily
with systems other than Emscripten. Eventually, it is possible that packages
will be able to upload wheels for Pyodide to PyPi.

See issue {pr}`655` and PR {pr}`2027`.

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

## Support for Rust packages

We have promising partial work toward compiling Python packages with Rust extensions for use with
Pyodide. So far we have only compiled small toy examples. Currently the compiled
Rust packages have various functional limitations and come out _very_ large.
Hopefully we can work toward increasing functionality so we can compile real
world Rust packages. It would also be good to reduce the Rust package sizes.

See {issue}`1973` and {pr}`2081`.

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
