(new-packages)=

# Creating a Pyodide package

## Quickstart

If you wish to use a package in Pyodide that is not already included, first you
need to determine whether it is necessary to package it for Pyodide. Ideally, you
should start this process with package dependencies.

### 1. Determining if creating a Pyodide package is necessary

Most pure Python packages can be installed directly from PyPi with
{func}`micropip.install` if they have a pure Python wheel. Check if this is the
case by going to the `pypi.org/project/<package-name>` URL and checking if the
"Download files" tab contains a file that ends with `*py3-none-any.whl`.

If the wheel is not on PyPi, but nevertheless you believe there is nothing
preventing it (it is a Python package without C extensions):

- you can create the wheel yourself by running,
  ```
  python -m pip install build
  python -m build
  ```
  from within the package folder where the `setup.py`
  are located. See the [Python packaging
  guide](https://packaging.python.org/tutorials/packaging-projects/#generating-distribution-archives)
  for more details.
  Then upload the wheel file somewhere (not to PyPi) and install it with
  micropip via its URL.
- you can also open an issue in the package repository asking the
  authors to upload the wheel.

If however the package has C extensions or its code requires patching, then
continue to the next steps.

```{note}
To determine if a package has C extensions, check if its `setup.py` contains
any compilation commands.
```

### 2. Creating the `meta.yaml` file

If your package is on PyPI, the
easiest place to start is with the {ref}`mkpkg tool <pyodide-mkpkg>`.
From the Pyodide root directory, install the tool with `pip install -e pyodide-build`, then run:


`pyodide-build mkpkg <package-name>`

This will generate a `meta.yaml` under `package/<package-name>/` (see
{ref}`meta-yaml-spec`) that should work out of the box for many simple Python
packages. This tool will populate the latest version, download link and sha256
hash by querying PyPI. It doesn't currently handle package dependencies, so you
will need to specify those yourself.

You can also use the `meta.yaml` of other Pyodide packages in the `packages/`
folder as a starting point.

```{note}
To reliably determine build and runtime dependencies, including for non Python
libraries, it is often useful to verify if the package was already built on
[conda-forge](https://conda-forge.org/) and open the corresponding `meta.yaml`
file. This can be done either by checking if the URL
`https://github.com/conda-forge/<package-name>-feedstock/blob/master/recipe/meta.yaml`
exists, or by searching the [conda-forge Github
org](https://github.com/conda-forge/) for the package name.

The `meta.yaml` in Pyodide was inspired by the one in conda, however it is
not strictly compatible.
```

### 3. Building the package and investigating issues

Once the `meta.yaml` is ready, we build the package with,

```
PYODIDE_PACKAGES="<package-name>" make
```

and see if there are any errors. The detailed build log can be found under
`packages/<package-name>/<package-name>.log`.

If there are errors you might need to,

- patch the package by adding `.patch` files to `packages/<package-name>/patches`
- add the patch files to the `source/patches` field in the `meta.yaml` file

then re-start the build.

In general, it is recommended to look into how other similar packages are built in Pyodide.
If you still encounter difficulties in building your package, open a [new Pyodide
issue](https://github.com/pyodide/pyodide/issues).

To learn more about how packages are built in Pyodide, read the following
sections.

## Build pipeline

Pyodide includes a toolchain to make it easier to add new third-party Python
libraries to the build. We automate the following steps:

- Download a source tarball (usually from PyPI)
- Confirm integrity of the package by comparing it to a checksum
- Apply patches, if any, to the source distribution
- Add extra files, if any, to the source distribution
- If the package includes C/C++/Cython extensions:
  - Build the package natively, keeping track of invocations of the native
    compiler and linker
  - Rebuild the package using emscripten to target WebAssembly
- If the package is pure Python:
  - Run the `setup.py` script to get the built package
- Package the results into an emscripten virtual filesystem package, which
  comprises:
  - A `.data` file containing the file contents of the whole package,
    concatenated together
  - A `.js` file which contains metadata about the files and installs them into
    the virtual filesystem.

Lastly, a `packages.json` file is output containing the dependency tree of all
packages, so {any}`pyodide.loadPackage` can
load a package's dependencies automatically.

## C library dependencies

Some Python packages depend on certain C libraries, e.g. `lxml` depends on
`libxml`.

To package a C library, create a directory in `packages/` for the C library.
This directory should contain (at least) two files:

- `Makefile` that specifies how the library should be be built. Note that the
  build system will call `make`, not `emmake make`. The convention is that the
  source for the library is downloaded by the Makefile, as opposed to being
  included in the Pyodide repository.

- `meta.yaml` that specifies metadata about the package. For C libraries, only
  three options are supported:

  - `package/name`: The name of the library, which must equal the directory
    name.
  - `requirements/run`: The dependencies of the library, which can include both
    C libraries and Python packages.
  - `build/library`: This must be set to `true` to indicate that this is a
    library and not an ordinary package.

After packaging a C library, it can be added as a dependency of a Python
package like a normal dependency. See `lxml` and `libxml` for an example (and
also `scipy` and `CLAPACK`).

_Remark:_ Certain C libraries come as emscripten ports, and do not have to be
built manually. They can be used by adding e.g. `-s USE_ZLIB` in the `cflags`
of the Python package. See e.g. `matplotlib` for an example.

## Structure of a Pyodide package

This section describes the structure of a pure Python package, and how our
build system creates it. In general, it is not recommended, to construct these
by hand; instead create a Python wheel and install it with micropip.

Pyodide is obtained by compiling CPython into web assembly. As such, it loads
packages the same way as CPython --- it looks for relevant files `.py` files in
`/lib/python3.x/`. When creating and loading a package, our job is to put our
`.py` files in the right location in emscripten's virtual filesystem.

Suppose you have a Python library that consists of a single directory
`/PATH/TO/LIB/` whose contents would go into
`/lib/python3.9/site-packages/PACKAGE_NAME/` under a normal Python
installation.

The simplest version of the corresponding Pyodide package contains two files
--- `PACKAGE_NAME.data` and `PACKAGE_NAME.js`. The first file
`PACKAGE_NAME.data` is a concatenation of all contents of `/PATH/TO/LIB`. When
loading the package via `pyodide.loadPackage`, Pyodide will load and run
`PACKAGE_NAME.js`. The script then fetches `PACKAGE_NAME.data` and extracts the
contents to emscripten's virtual filesystem. Afterwards, since the files are
now in `/lib/python3.9/`, running `import PACKAGE_NAME` in Python will
successfully import the module as usual.

To construct this bundle, we use the `file_packager.py` script from emscripten.
We invoke it as follows:

```sh
$ ./tools/file_packager.sh \
     PACKAGE_NAME.data \
     --js-output=PACKAGE_NAME.js \
     --preload /PATH/TO/LIB/@/lib/python3.9/site-packages/PACKAGE_NAME/
```

The arguments can be explained as follows:

- PACKAGE_NAME.data indicates where to put the data file
- --js-output=PACKAGE_NAME.js indicates where to put the javascript file
- `--preload` instructs the package to look for the
  file/directory before the separator `@` (namely `/PATH/TO/LIB/`) and place
  it at the path after the `@` in the virtual filesystem (namely
  `/lib/python3.9/site-packages/PACKAGE_NAME/`).

`file_packager.sh` adds the following options:

- `--lz4` to use LZ4 to compress the files
- `--export-name=globalThis.__pyodide_module` tells `file_packager` where to find the main Emscripten
  module for linking.
- `--exclude *__pycache__*` to omit the pycache directories
- `--use-preload-plugins` says to [automatically decode files based on their
  extension](https://emscripten.org/docs/porting/files/packaging_files.html#preloading-files)

```{eval-rst}
.. toctree::
   :hidden:

   meta-yaml.md
```
