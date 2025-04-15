(building-packages)=

# Building packages for Pyodide

This document describes how to build packages for Pyodide.
It is intended for package maintainers and developers who want to build packages
for Pyodide or add packages to the Pyodide distribution.

## Determining if building a package is necessary

Before starting to build packages for Pyodide, please check if it is necessary.

1. If the package is a pure Python package and does not use any native extensions
   such as C, Cython, or Rust, it is likely to work with Pyodide without building it.
   In that case, try installing it from PyPI with {func}`micropip.install` in Pyodide.
   Try `await micropip.install("package-name")` to see if it works.

2. There are packages already built for Pyodide and included in the Pyodide distribution.
   Visit [`pyodide-recipes`](https://github.com/pyodide/pyodide-recipes) repository to see
   if the package you need is already built and available.

## Limitations

Pyodide currently only supports building packages in Linux environments officially,
though there is a good chance it will work in MacOS too.
If you are using Windows, try Windows Subsystem for Linux.

## Prerequisites

0. Prepare proper host Python version

Before starting to build packages for Pyodide, you need to have a host Python version that is compatible
with the target Pyodide version. For example, if you want to build packages for Pyodide 0.27.5, which contains
Python 3.12.7, you need Python 3.12 installed on your host system. Using different Python versions will result
in build errors.

1. Install `pyodide-build`:

`pyodide-build` is a build tool for cross-compiling packages for Pyodidde. You can install it using pip:

```bash
pip install pyodide-build
```

After installation, `pyodide` command will be available in your shell. If not, pip might have installed it in a
local directory. Please check the installation directory and add it to your PATH.

2. Install the build toolchain for target Pyodide:

```bash
pyodide xbuildenv install <target-pyodide-version>
```

This command will fail if the host Python version is not compatible with the target Pyodide version.
In that case, run

```bash
pyodide xbuildenv search -a
```

to find the compatible Python version and update the local Python version to match the target Pyodide version.

3. Setup [Emscripten](https://github.com/emscripten-core/emscripten):

Emscripten is a compiler toolchain for compiling native code to WebAssembly.
You need to download and activate the Emscripten version that matches the target Pyodide version.

```bash
git clone https://github.com/emscripten-core/emsdk
cd emsdk

PYODIDE_EMSCRIPTEN_VERSION=$(pyodide config get emscripten_version)
./emsdk install ${PYODIDE_EMSCRIPTEN_VERSION}
./emsdk activate ${PYODIDE_EMSCRIPTEN_VERSION}
source emsdk_env.sh
which emcc
```

Running `source emsdk_env.sh` will set up the environment variables needed for Emscripten.
If you restart your shell, you need to run `source emsdk_env.sh` again to set up the environment variables.

Now you are ready to build packages for Pyodide.

## Building Packages from Source

See {ref}`building-packages-from-source`.

## Adding Packages into Pyodide Distribution

See {ref}`adding-packages-into-pyodide-distribution`.

## Building Packages using cibuildwheel

[cibuildwheel](https://cibuildwheel.pypa.io/en/stable/) 2.19 or later provides
support for building binary wheels with Pyodide as a target. Follow the
[cibuildwheel documentation](https://cibuildwheel.pypa.io/en/stable/setup/#pyodide-webassembly-builds-experimental)
to set up your project to build wheels for Pyodide.
