(building-and-testing-packages)=

# Building and testing Python packages out of tree

This is some information about how to build and test Python packages against
Pyodide out of tree (for instance in your package's CI or for use with private
packages).

## Building binary packages for Pyodide

If your package is a pure Python package (i.e., if the wheel ends in
`py3-none-any.whl`) then follow the official PyPA documentation on building
[wheels](https://packaging.python.org/en/latest/tutorials/packaging-projects/#generating-distribution-archives)
Otherwise, the procedure is simple. In your package directory run the following
command line commands:

```sh
pip install pyodide-build
pyodide build
```

Pyodide currently only supports Linux for out of tree builds, though there is a
good change it will work in MacOS too. If you are using Windows, try Windows
Subsystem for Linux.

`pyodide build` invokes a slightly modified version of the `pypa/build` build
frontend so the behavior should be similar to what happens if you do:

```sh
pip install build
python -m build
```

If you run into problems, make sure that building a native wheel with
`pypa/build` works.

`pyodide build` respects the environment variables `CFLAGS`, `CXXFLAGS`, and
`LDFLAGS`, so if you need to customize compiler arguments you can set these. Any
additional arguments passed to `pyodide build` will be passed along to the build
backend.

If you run into problems, please open an issue about it.

## Testing packages against Pyodide

Pyodide provides an experimental command line runner for testing packages
against Pyodide. Using it requires nodejs version 14 or newer.

The way it works is simple: you can create a virtual environment with:

```sh
pyodide venv .venv-pyodide
```

Activate it just like a normal virtual environment:

```sh
source .venv-pyodide/bin/python
```

As a warning, things are pretty weird inside of the Pyodide virtual environment
because `python` points to the Pyodide Python runtime. Any program that uses
Python and is sensitive to the current virtual environment will probably break.

You can install whatever dependencies you need with pip. For a pure Python
package, the following will work:

````sh
pip install -e .

For a binary package, you will need to build a wheel with `pyodide build` and
then point `pip` directly to the built wheel. For now, editable installs won't
work with binary packages.

```sh
# Build the binary package
pyodide build
# Install it
pip install dist/the_wheel-cp310-cp310-emscripten_3_1_20_wasm32.whl[tests]
````

To test, you can generally run the same script as you would usually do. For many
packages this will be:

```sh
python -m pytest
```

but for instance `numpy` uses a file called `runtests.py`; the following works:

```sh
python runtests.py
```

and you can pass options to it just like normal. Currently `subprocess` doesn't
work, so if you have a test runner that uses `subprocess` then it cannot be
used.
