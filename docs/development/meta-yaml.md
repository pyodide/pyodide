(meta-yaml-spec)=

# The meta.yaml specification

Packages are defined by writing a `meta.yaml` file. The format of these files is
based on the `meta.yaml` files used to build [Conda
packages](https://docs.conda.io/projects/conda-build/en/latest/resources/define-metadata.html),
though it is much more limited. The most important limitation is that Pyodide
assumes there will only be one version of a given library available, whereas
Conda allows the user to specify the versions of each package that they want to
install. Despite the limitations, it is recommended to use existing conda
package definitions as a starting point to create Pyodide packages. In general,
however, one should not expect Conda packages to "just work" with Pyodide, see
{pr}`795`

```{admonition} This is unstable
:class: warning

The Pyodide build system is under fairly active development (as of 2022/03/13).
The next couple of releases are likely to include breaking changes.
```

The supported keys in the `meta.yaml` file are described below.

## `package`

### `package/name`

The name of the package. It must match the name of the package used when
expanding the tarball, which is sometimes different from the name of the package
in the Python namespace when installed. It must also match the name of the
directory in which the `meta.yaml` file is placed. It can only contain
alphanumeric characters, `-`, and `_`.

### `package/version`

The version of the package.

## `source`

### `source/url`

The URL of the source tarball.

The tarball may be in any of the formats supported by Python's
`shutil.unpack_archive`: `tar`, `gztar`, `bztar`, `xztar`, and `zip`.

### `source/extract_dir`

The top level directory name of the contents of the source tarball (i.e. once
you extract the tarball, all the contents are in the directory named
`source/extract_dir`). This defaults to the tarball name (sans extension).

### `source/path`

Alternatively to `source/url`, a relative or absolute path can be specified
as package source. This is useful for local testing or building packages which
are not available online in the required format.

If a path is specified, any provided checksums are ignored.

### `source/md5`

The MD5 checksum of the tarball. It is recommended to use SHA256 instead of MD5.
At most one checksum entry should be provided per package.

### `source/sha256`

The SHA256 checksum of the tarball. It is recommended to use SHA256 instead of MD5.
At most one checksum entry should be provided per package.

### `source/patches`

A list of patch files to apply after expanding the tarball. These are applied
using `patch -p1` from the root of the source tree.

### `source/extras`

Extra files to add to the source tree. This should be a list where each entry is
a pair of the form `(src, dst)`. The `src` path is relative to the directory in
which the `meta.yaml` file resides. The `dst` path is relative to the root of
source tree (the expanded tarball).

## `build`

### `build/cflags`

Extra arguments to pass to the compiler when building for WebAssembly.

(This key is not in the Conda spec).

### `build/cxxflags`

Extra arguments to pass to the compiler when building C++ files for WebAssembly.
Note that both `cflags` and `cxxflags` will be used when compiling C++ files.
A common example would be to use `-std=c++11` for code that makes use of C++11 features.

(This key is not in the Conda spec).

### `build/ldflags`

Extra arguments to pass to the linker when building for WebAssembly.

(This key is not in the Conda spec).

### `build/exports`

Which symbols should be exported from the shared object files. Possible values
are:

- `pyinit`: The default. Only export Python module initialization symbols of
  the form `PyInit_some_module`.
- `requested`: Export the functions that are marked as exported in the object
  files. Switch to this if `pyinit` doesn't work. Useful for packages that use
  `ctypes` or `dlsym` to access symbols.
- `whole_archive`: Uses `-Wl,--whole-archive` to force inclusion of all
  symbols. Use this when neither `pyinit` nor `explicit` work.

### `build/backend-flags`

Extra flags to pass to the build backend (e.g., `setuptools`, `flit`, etc).

### `build/library`

Should be set to true for library packages. Library packages are packages that are needed for other packages but are not Python packages themselves. For library packages, the script specified in the `build/script` section is run to compile the library. See the [zlib meta.yaml](https://github.com/pyodide/pyodide/blob/main/packages/zlib/meta.yaml) for an example of a library package specification.

### `build/sharedlibrary`

Should be set to true for shared library packages. Shared library packages are packages that are needed for other packages, but are loaded dynamically when Pyodide is run. For shared library packages, the script specified in the `build/script` section is run to compile the library. The script should build the shared library and copy it into a subfolder of the source folder called `install`. Files or folders in this install folder will be packaged to make the Pyodide package. See the [CLAPACK meta.yaml](https://github.com/pyodide/pyodide/blob/main/packages/CLAPACK/meta.yaml) for an example of a shared library specification.

### `build/script`

The script section is required for a library package (`build/library` set to true). For a Python package this section is optional. If it is specified for a Python package, the script section will be run before the build system runs `setup.py`. This script is run by `bash` in the directory where the tarball was extracted.

### `build/post`

Shell commands to run after building the library. These are run with
`bash`, and there are two special environment variables defined:

- `$SITEPACKAGES`: The `site-packages` directory into which the package has been installed.
- `$PKGDIR`: The directory in which the `meta.yaml` file resides.

(This key is not in the Conda spec).

### `build/replace-libs`

A list of strings of the form `<old_name>=<new_name>`, to rename libraries when linking. This in particular
might be necessary when using emscripten ports.
For instance, `png16=png` is currently used in matplotlib.

### `build/unvendor-tests`

Whether to unvendor tests found in the installation folder to a separate
package `<package-name>-tests`. If this option is true and no tests are found,
the test package will not be created. Default: true.

## `requirements`

### `requirements/run`

A list of required packages.

(Unlike conda, this only supports package names, not versions).

## `test`

### `test/imports`

List of imports to test after the package is built.

## Supported Environment Variables

The following environment variables can be used in the scripts in the meta.yaml
files:

- PYODIDE_ROOT: The path to the base Pyodide directory
- PYMAJOR: Current major Python version
- PYMINOR: Current minor Python version
- PYMICRO: Current micro Python version
- SIDE_MODULE_CFLAGS: The standard CFLAGS for a side module. Use when compiling
  libraries or shared libraries.
- SIDE_MODULE_LDFLAGS: The standard LDFLAGS for a side module. Use when linking
  a shared library.
- NUMPY_LIB: Use `-L$NUMPY_LIB` as a ldflag when linking `-lnpymath` or
  `-lnpyrandom`.
