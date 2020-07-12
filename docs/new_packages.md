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
packages, so `pyodide.loadPackage` can load a package's dependencies
automatically.

## mkpkg

If you wish to create a new package for pyodide, the easiest place to start is
with the `mkpkg` tool. If your package is on PyPI, just run:

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

The url of the source tarball.

The tarball may be in any of the formats supported by Python's
`shutil.unpack_archive`: `tar`, `gztar`, `bztar`, `xztar`, and `zip`.

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

#### `build/ldflags`

Extra arguments to pass to the linker when building for WebAssembly.

(This key is not in the Conda spec).

#### `build/post`

Shell commands to run after building the library. These are run inside of
`bash`, and there are two special environment variables defined:

- `$SITEPACKAGES`: The `site-packages` directory into which the package has been installed.
- `$PKGDIR`: The directory in which the `meta.yaml` file resides.

(This key is not in the Conda spec).

### `requirements`

#### `requirements/run`

A list of required packages.

(Unlike conda, this only supports package names, not versions).
