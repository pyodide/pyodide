(building-packages-from-source)=

# Building Python Packages from Source

This document describes building Python packages following the [PEP 517](https://peps.python.org/pep-0517/) to Pyodide.
In other words, the package should be buildable with `python -m build` command.
Otherwise, the package would likely require a complex setup to build it.
Please contact the package maintainer to discuss how to build the package with Pyodide build system.

> [!NOTE]
> It is assumed that the person reading this article understands the build system for the package they are trying to build,
> or at least has built the package in the native environment themselves.
> If not, please refer to the package's documentation for building instructions.

## Quickstart

Go to the directory into the package folder where the `pyproject.toml` or `setup.py`
file is located. Then run

```sh
pyodide build
```

in the package folder. This command produces a wheel in the `dist/` folder,
similarly to the [PyPA build](https://pypa-build.readthedocs.io/en/latest/)
command.

If you need to add custom compiler / linker flags to the compiler invocations,
you can set the `CFLAGS`, `CXXFLAGS` and `LDFLAGS` environment variables. For instance, to
make a debug build, you can use: `CFLAGS=-g2 LDFLAGS=g2 pyodide build`.

`pyodide build` invokes a slightly modified version of the `pypa/build` build
frontend so the behavior should be similar to what happens if you do:

```sh
pip install build
python -m build
```

### Notes

- the resulting package wheels have a file name of the form
  `*-cpXXX-cpXXX-pyodide_XXXX_X_wasm_32.whl` and are compatible only for a
  given Pyodide versions. In the Pyodide distribution, Python and
  Emscripten are updated simultaneously.
- for now, PyPI does not support emscripten/wasm32 wheels so you will not be able to upload
  them there. (See [PEP 783](https://peps.python.org/pep-0783/) for future plans.)

## Debugging build issues

If you run into problems with `pyodide build`, first make sure 
that building a native wheel with `pypa/build` works.
If it does, compare the output of `pyodide build` with the output of `python -m build`.

Once you've found the differences and errors, analyze them to see if they apply to any of the cases below.
If none of them apply or are difficult to resolve, please open an issue in Pyodide repository.

### Failed locating libraries / Missing libraries

If you see errors like `error: cannot find -l<libname>` or `error: <libname> not found`,
it means that the build system cannot locate the library, or the library is not properly built against WebAssembly.

If you are relying on CMake's `find_package` or Meson's `find_library` to locate the library, it might not be able to find the library,
because the cross-compiled libraries are not in the default search path.

In that case, you need to explicitly specify the library paths in some way. If you are the package maintainer,
please update your build system to locate the libraries in the cross-compiled library path.

### Linker error: function signature mismatch

If you see errors like

```
wasm-ld: error: function signature mismatch: some_func
>>> defined as (i32, i32) -> i32 in some_static_lib.a(a.o)
>>> defined as (i32) -> i32 in b.o
```

it means that there is a function signature mismatch in your C/C++ code.
WASM is very strict about function signatures, and the linker will fail if it finds a mismatch.

Check {ref}`function-signature-mismatch` for more details on how to debug this issue.

## Testing packages against Pyodide

Pyodide provides an experimental command line runner for testing packages
against Pyodide. Using it requires nodejs version 20 or newer.

The way it works is simple: you can create a virtual environment with:

```sh
pyodide venv .venv-pyodide
```

Activate it just like a normal virtual environment:

```sh
source .venv-pyodide/bin/activate
```

As a warning, things are pretty weird inside of the Pyodide virtual environment
because `python` points to the Pyodide Python runtime. Any program that uses
Python and is sensitive to the current virtual environment will probably break.

You can install whatever dependencies you need with pip. For a pure Python
package, the following will work:

```sh
pip install -e .
```

For a binary package, you will need to build a wheel with `pyodide build` and
then point `pip` directly to the built wheel. For now, editable installs won't
work with binary packages.

```sh
# Build the binary package
pyodide build
# Install it
pip install dist/the_wheel-cp312-cp312-pyodide_2024_0_wasm32.whl[tests]
```

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

## Github Actions build examples

This is a complete example for building a Pyodide wheel out of tree using
`pyodide build` directly:

```yaml
runs-on: ubuntu-22.04 # or ubuntu-latest
  steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with:
       python-version: 3.13
  - run: |
      pip install pyodide-build>=0.29.2
      echo EMSCRIPTEN_VERSION=$(pyodide config get emscripten_version) >> $GITHUB_ENV
  - uses: mymindstorm/setup-emsdk@v14
    with:
       version: ${{ env.EMSCRIPTEN_VERSION }}
  - run: pyodide build
```

And this is an example using `cibuildwheel` to build a Pyodide wheel out of tree:

```yaml
runs-on: ubuntu-22.04 # or ubuntu-latest
  steps:
  - uses: actions/checkout@v4
  - uses: pypa/cibuildwheel@v2.20.0
    env:
       CIBW_PLATFORM: pyodide
```

For an example "in the wild" of a github action to build and test a wheel
against Pyodide, see
[the numpy CI](https://github.com/numpy/numpy/blob/main/.github/workflows/emscripten.yml)
