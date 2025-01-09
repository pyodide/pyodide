(building-packages-from-source)=

# Building Python Packages from Source

This is some information about how to build and test Python packages against
Pyodide, for instance in your package's CI or for use with private
packages.

Pyodide currently only supports building packages in Linux environments officially,
though there is a good change it will work in MacOS too.
If you are using Windows, try Windows Subsystem for Linux.

## Building binary packages for Pyodide

If your package is a pure Python package (i.e., if the wheel ends in
`py3-none-any.whl`) then follow the official PyPA documentation on building
[wheels](https://packaging.python.org/en/latest/tutorials/packaging-projects/#generating-distribution-archives)
For binary packages, the manual steps are detailed below. In addition,
[cibuildwheel](https://cibuildwheel.pypa.io/en/stable/) 2.19 or later provides
support for building binary wheels with Pyodide as a target.

### Build the WASM/Emscripten wheel

Change directory into the package folder where the `pyproject.toml` or `setup.py`
file is located. You should be in a shell session where you ran
`source emsdk_env.sh`. Then run

```sh
pyodide build
```

in the package folder . This command produces a wheel in the `dist/` folder,
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

If you run into problems, make sure that building a native wheel with
`pypa/build` works. If it does, then please open an issue about it.

### Serve the wheel

Serve the wheel via a file server e.g., `python -m http.server --directory dist`.
Then you can install it with `pyodide.loadPackage` or `micropip.install` by URL.

### Notes

- the resulting package wheels have a file name of the form
  `*-cp312-cp312-pyodide_2024_0_wasm_32.whl` and are compatible only for a
  given Pyodide versions. In the Pyodide distribution, Python and
  Emscripten are updated simultaneously.
- for now, PyPI does not support emscripten/wasm32 wheels so you will not be able to upload
  them there.

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
       python-version: 3.12
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
