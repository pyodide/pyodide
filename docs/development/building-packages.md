(building-packages)=

# Building packages against Pyodide

This is some information about how to build Python packages against Pyodide.
Because the WebAssembly environment that Pyodide runs on is a different platform than other Linux, MacOS, Windows, etc. platforms,
you will need to cross-compile your package to run on Pyodide.
Pyodide provides a tool for this, `pyodide-build`, which allows you to build packages targeting Pyodide.

## Determining if building a package is necessary

Before starting to build packages for Pyodide, please check if it is necessary.

1. If the package is a pure Python package and does not use any C extensions,
   you can simply install it from PyPI with {func}`micropip.install` in Pyodide.
   Try `micropip.install("package-name")` to see if it works.

2. There are lots of packages already built for Pyodide. Check the
   [`pyodide-recipes`](https://github.com/pyodide/pyodide-recipes) repository to see
   if the package you need is already built and available.

## Prerequisites

To start building packages for Pyodide, you need to prepare the proper version of Python and Emscripten.
Each Pyodide version is built against different versions of Python and Emscripten,
and it is important to use the same versions to build packages for specific Pyodide versions.

1. Install `pyodide-build`:

```bash
pip install pyodide-build
```

2. Install the build toolchain for target Pyodide:

```bash
pyodide xbuildenv install <target-pyodide-version>
```

This command may fail if the local Python version is not compatible with the target Pyodide version.
In that case, run

```bash
pyodide xbuildenv search -a
```

to find the compatible Python version and update the local Python version to match the target Pyodide version.

3. Setup [Emscripten](https://github.com/emscripten-core/emscripten):

You need to download and activate the Emscripten developer toolkit that matches the target Pyodide version.

```bash
git clone https://github.com/emscripten-core/emsdk
cd emsdk

PYODIDE_EMSCRIPTEN_VERSION=$(pyodide config get emscripten_version)
./emsdk install ${PYODIDE_EMSCRIPTEN_VERSION}
./emsdk activate ${PYODIDE_EMSCRIPTEN_VERSION}
source emsdk_env.sh
```

If you restart your shell, you will need to run `source emsdk_env.sh` again.

Now you are ready to build packages for Pyodide.

## Building Packages from Source

See {ref}`building-packages-from-source`.

## Building Packages using Recipe

See {ref}`building-packages-using-recipe`.

## Adding Packages into Pyodide Distribution

See {ref}`adding-packages-into-pyodide-distribution`.
