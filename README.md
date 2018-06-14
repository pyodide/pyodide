# Pyodide

[![Build Status](https://circleci.com/gh/iodide-project/pyodide.png)](https://circleci.com/gh/iodide-project/pyodide)

The Python scientific stack, compiled to WebAssembly.

It provides transparent conversion of objects between Javascript and Python and
a sharing of global namespaces. When inside a browser, this means Python has
full access to the Web APIs.

See [the demo](https://iodide.io/pyodide-demo/python.html)

# Building

These instructions were tested on Linux. OSX should be substantively the same.

Make sure the prerequisites for [emsdk](https://github.com/juj/emsdk) are installed.

Install [lessc](https://lesscss.org/) to compile less to css.

Type `make`.

(The build downloads and builds a local, patched version of emsdk, then
downloads and builds Python and third-party packages).

# Testing

1. Install the following dependencies into the default Python installation:

   `pip install pytest selenium`

2. Install [geckodriver](https://github.com/mozilla/geckodriver/releases) somewhere
   on your `PATH`.

3. `make test`

# Benchmarking

1. Install the same dependencies as for testing.

2. `make benchmark`

# Linting

1. Python is linted with `flake8`.  C and Javascript are linted with `clang-format`.

2. `make lint`
