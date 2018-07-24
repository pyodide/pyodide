# Pyodide

[![Build Status](https://circleci.com/gh/iodide-project/pyodide.png)](https://circleci.com/gh/iodide-project/pyodide)

The Python scientific stack, compiled to WebAssembly.

It provides transparent conversion of objects between Javascript and Python.
When inside a browser, this means Python has full access to the Web APIs.

**While closely related to the [iodide project](https://iodide.io), Pyodide may
be used standalone in any context where you want to run Python inside a web
browser.**

See [the demo](https://iodide.io/pyodide-demo/python.html)

# Building

These instructions were tested on Linux. OSX should be mostly the same.

Make sure the prerequisites for [emsdk](https://github.com/juj/emsdk) are
installed. Pyodide will build a custom, patched version of emsdk, so there is no
need to build it yourself prior.

Additional build prerequisites are:

- A working native compiler toolchain, enough to build CPython.
- A native Python 3.6 or later to run the build scripts.
- PyYAML
- [lessc](https://lesscss.org/) to compile less to css.
- [uglifyjs](https://github.com/mishoo/UglifyJS) to minify Javascript builds.
- [ccache](https://ccache.samba.org) (optional) recommended for much faster rebuilds.


`make`

# Testing

Install the following dependencies into the default Python installation:

   `pip install pytest selenium`

Install [geckodriver](https://github.com/mozilla/geckodriver/releases) somewhere
on your `PATH`.

`make test`

# Benchmarking

Install the same dependencies as for testing.

`make benchmark`

# Linting

Python is linted with `flake8`.  C and Javascript are linted with `clang-format`.

`make lint`
