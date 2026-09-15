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

(http-client-limit)=

## Write http.client in terms of Web APIs

Python packages make an extensive use of packages such as `requests` to
synchronously fetch data. We currently can't use such packages since sockets
are not available in Pyodide. We could however try to re-implement some
stdlib libraries with Web APIs, potentially making this possible.

Because http.client is a synchronous API, we first need support for synchronous
IO.

See issue {issue}`140`.
