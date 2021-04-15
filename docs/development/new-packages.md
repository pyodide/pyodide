(new-packages)=
# Creating a Pyodide package

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
packages, so  {any}`pyodide.loadPackage` can
load a package's dependencies automatically.

## mkpkg

If you wish to create a new package for Pyodide, the easiest place to start is
with the {ref}`mkpkg tool <pyodide-mkpkg>`. If your package is on PyPI, just run:

`bin/pyodide mkpkg $PACKAGE_NAME`

This will generate a `meta.yaml` (see below) that should work out of the box
for many pure Python packages. This tool will populate the latest version, download
link and sha256 hash by querying PyPI. It doesn't currently handle package
dependencies, so you will need to specify those yourself.

## The meta.yaml file

Packages are defined by writing a `meta.yaml` file. The format of these files is
based on the `meta.yaml` files used to build [Conda
packages](https://conda.io/docs/user-guide/tasks/build-packages/define-metadata.html),
though it is much more limited. The most important limitation is that Pyodide
assumes there will only be one version of a given library available, whereas
Conda allows the user to specify the versions of each package that they want to
install. Despite the limitations, keeping the file format as close as possible
to conda's should make it easier to use existing conda package definitions as a
starting point to create Pyodide packages. In general, however, one should not
expect Conda packages to "just work" with Pyodide. (In the longer term, Pyodide
may use conda as its packaging system, and this should hopefully ease that
transition.)

The supported keys in the `meta.yaml` file are described below.

### `package`

#### `package/name`

The name of the package. It must match the name of the package used when
expanding the tarball, which is sometimes different from the name of the package
in the Python namespace when installed. It must also match the name of the
directory in which the `meta.yaml` file is placed. It can only contain
alpha-numeric characters and `-`, `_`.

#### `package/version`

The version of the package.

### `source`

#### `source/url`

The URL of the source tarball.

The tarball may be in any of the formats supported by Python's
`shutil.unpack_archive`: `tar`, `gztar`, `bztar`, `xztar`, and `zip`.

### `source/extract_dir`

The top level directory name of the contents of the source tarball (i.e. once
you extract the tarball, all the contents are in the directory named
`source/extract_dir`). This defaults to the tarball name (sans extension).

#### `source/path`

Alternatively to `source/url`, a relative or absolute path can be specified
as package source. This is useful for local testing or building packages which
are not available online in the required format.

If a path is specified, any provided checksums are ignored.

#### `source/md5`

The MD5 checksum of the tarball. It is recommended to use SHA256 instead of MD5.
At most one checksum entry should be provided per package.

#### `source/sha256`

The SHA256 checksum of the tarball. It is recommended to use SHA256 instead of MD5.
At most one checksum entry should be provided per package.

#### `source/patches`

A list of patch files to apply after expanding the tarball. These are applied
using `patch -p1` from the root of the source tree.

#### `source/extras`

Extra files to add to the source tree. This should be a list where each entry is
a pair of the form `(src, dst)`. The `src` path is relative to the directory in
which the `meta.yaml` file resides. The `dst` path is relative to the root of
source tree (the expanded tarball).

### `build`

#### `build/skip_host`

Skip building C extensions for the host environment. Default: `True`.

Setting this to `False` will result in ~2x slower builds for packages that
include C extensions. It should only be needed when a package is a build
time dependency for other packages. For instance, numpy is imported during
installation of matplotlib, importing numpy also imports included C extensions,
therefore it is built both for host and target.


#### `build/cflags`

Extra arguments to pass to the compiler when building for WebAssembly.

(This key is not in the Conda spec).

#### `build/cxxflags`

Extra arguments to pass to the compiler when building C++ files for WebAssembly. Note that both clfags and cxxflags will be used when compiling C++ files. A common example would be to use -std=c++11 for code that makes use of C++11 features.

(This key is not in the Conda spec).

#### `build/ldflags`

Extra arguments to pass to the linker when building for WebAssembly.

(This key is not in the Conda spec).

#### `build/library`

Should be set to true for library packages. Library packages are packages that are needed for other packages but are not Python packages themselves. For library packages, the script specified in the `build/script` section is run to compile the library. See the [zlib meta.yaml](https://github.com/pyodide/pyodide/blob/master/packages/zlib/meta.yaml) for an example of a library package specification.

#### `build/sharedlibrary`

Should be set to true for shared library packages. Shared library packages are packages that are needed for other packages, but are loaded dynamically when Pyodide is run. For shared library packages, the script specified in the `build/script` section is run to compile the library. The script should build the shared library and copy into into a subfolder of the source folder called `install`. Files or folders in this install folder will be packaged to make the Pyodide package. See the [CLAPACK meta.yaml](https://github.com/pyodide/pyodide/blob/master/packages/CLAPACK/meta.yaml) for an example of a shared library specification.

#### `build/script`

The script section is required for a library package (`build/library` set to true). For a Python package this section is optional. If it is specified for a Python package, the script section will be run before the build system runs `setup.py`. This script is run by `bash` in the directory where the tarball was extracted.

#### `build/post`

Shell commands to run after building the library. These are run inside of
`bash`, and there are two special environment variables defined:

- `$SITEPACKAGES`: The `site-packages` directory into which the package has been installed.
- `$PKGDIR`: The directory in which the `meta.yaml` file resides.

(This key is not in the Conda spec).

#### `build/replace-libs`

A list of strings of the form `<old_name>=<new_name>`, to rename libraries when linking. This in particular
might be necessary when using emscripten ports.
For instance, `png16=png` is currently used in matplotlib.

### `requirements`

#### `requirements/run`

A list of required packages.

(Unlike conda, this only supports package names, not versions).

### `test`

#### `test/imports`

List of imports to test after the package is built.

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

*Remark:* Certain C libraries come as emscripten ports, and do not have to be
built manually. They can be used by adding e.g. `-s USE_ZLIB` in the `cflags`
of the Python package. See e.g. `matplotlib` for an example.

## Structure of a Pyodide package
This section describes the structure of a pure Python package, and how our
build system creates it (In general, it is not recommended, to construct these
by hand; instead create a Python wheel and install it with micropip)

Pyodide is obtained by compiling CPython into web assembly. As such, it loads
packages the same way as CPython --- it looks for relevant files `.py` files in
`/lib/python3.x/`. When creating and loading a package, our job is to put our
`.py` files in the right location in emscripten's virtual filesystem.

Suppose you have a Python library that consists of a single directory
`/PATH/TO/LIB/` whose contents would go into
`/lib/python3.8/site-packages/PACKAGE_NAME/` under a normal Python
installation.

The simplest version of the corresponding Pyodide package contains two files
--- `PACKAGE_NAME.data` and `PACKAGE_NAME.js`. The first file
`PACKAGE_NAME.data` is a concatenation of all contents of `/PATH/TO/LIB`. When
loading the package via `pyodide.loadPackage`, Pyodide will load and run
`PACKAGE_NAME.js`. The script then fetches `PACKAGE_NAME.data` and extracts the
contents to emscripten's virtual filesystem. Afterwards, since the files are
now in `/lib/python3.8/`, running `import PACKAGE_NAME` in Python will
successfully import the module as usual.

To construct this bundle, we use the `file_packager.py` script from emscripten.
We invoke it as follows:
```sh
$ ./file_packager.py PACKAGE_NAME.data \
     --js-output=PACKAGE_NAME.js \
     --export-name=pyodide._module \
     --use-preload-plugins \
     --preload /PATH/TO/LIB/@/lib/python3.8/site-packages/PACKAGE_NAME/ \
     --exclude "*__pycache__*" \
     --lz4
```

The arguments can be explained as follows:
 - The `--preload` argument instructs the package to look for the
   file/directory before the separator `@` (namely `/PATH/TO/LIB/`) and place
   it at the path after the `@` in the virtual filesystem (namely
   `/lib/python3.8/site-packages/PACKAGE_NAME/`).
 - The `--exclude` argument specifies files to omit from the package.
 - The `--lz4` argument says to use LZ4 to compress the files
