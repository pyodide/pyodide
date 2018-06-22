# Creating a Pyodide package

Pyodide includes a set of automatic tools to make it easier to add new
third-party Python libraries to the build.

These tools automate the following steps for building a package:

- Downloading a source tarball (usually from PyPI)
- Confirming integrity of the package by comparing it to a checksum
- Applying patches, if any, to the source distribution
- Adding extra files, if any, to the source distribution
- If the package includes C/C++/Cython extensions:
  - Building the package natively, keeping track of invocations of the native
    compiler and linker
  - Rebuilding the package using emscripten to target WebAssembly
- If the package is pure Python:
  - Running the `setup.py` script to get the built package
- Packaging the results into an emscripten virtual filesystem package, which
  comprises:
  - A `.data` file containing the file contents of the whole package,
    concatenated together
  - A `.js` file which contains metadata about the files and installs them into
    the virtual filesystem.

Lastly, a `packages.json` file is output containing the dependency tree of all
packages, so `pyodide.loadPackage` can load a package's dependencies
automatically.

## The meta.yaml file

Packages are defined by writing a `meta.yaml` file. The format of these files is
based on the `meta.yaml` files used to build [Conda packages](TODO: Add URL),
though it is much more limited. The most important limitation is that Pyodide
assumes there will only be one version of a given library available. Despite the
limitations, keeping the file format as close as possible to conda's should make
it easier to use existing conda package definitions as a starting point to
create Pyodide packages. In general, however, one should not expect Conda
packages to "just work" with Pyodide. (In the longer term, Pyodide may use conda
as its packaging system, and this should hopefully ease that transition.)

The supported keys in the `meta.yaml` file are described below.

### `package`

#### `package/name`

The name of the package. It must match the name of the package used when
expanding the tarball, which is sometimes different from the name of the package
in the Python namespace when installed. It must also match the name of the
directory in which the `meta.yaml` file is placed.

#### `package/version`

The version of the package.

### `source`

#### `source/url`

The url of the source tarball.

The tarball may be in any of the formats supported by Python's
`shutil.unpack_archive`:

  tar, gztar, bztar, xztar, zip

#### `source/md5`

The MD5 checksum of the tarball.  (TODO: More hash types should be supported in the future).

#### `source/patches`

A list of patch files to apply after expanding the tarball. These are applied
using `patch -p1` from the root of the source tree.

#### `source/extras`

Extra files to add to the source tree. This should be a list where each entry is
a pair of the form `(src, dst)`. The `src` path is relative to the directory in
which the `meta.yaml` file resides. The `dst` path is relative to the root of
source tree (the expanded tarball).

### `build`

#### `build/cflags`

Extra arguments to pass to the compiler when building for WebAssembly.

#### `build/ldflags`

Extra arguments to pass to the linker when building for WebAssembly.

#### `build/post`

Shell commands to run after building the library. These are run inside of
`bash`, and there are two special environment variables defined:

- `$BUILD`: The root of the built package. (`build/lib.XXX/` inside of the
  source directory). This is what will be installed into Python site-packages.
- `$PKGDIR`: The directory in which the `meta.yaml` file resides.

(This key is not part of the conda package specification).

### `requirements`

#### `requirements/run`

A list of required packages.

(Unlike conda, this only supports package names, not versions).
