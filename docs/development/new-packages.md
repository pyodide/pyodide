(new-packages)=

# Creating a Pyodide package

It is recommended to look into how other similar packages are built in Pyodide.
If you encounter difficulties in building your package after trying the steps
listed here, open a [new Pyodide issue](https://github.com/pyodide/pyodide/issues).

## Quickstart

If you wish to use a package in Pyodide that is not already included, first you
need to determine whether it is necessary to package it for Pyodide. Ideally,
you should start this process with package dependencies.

### 1. Determining if creating a Pyodide package is necessary

Most pure Python packages can be installed directly from PyPI with
{func}`micropip.install` if they have a pure Python wheel. Check if this is the
case by trying `micropip.install("package-name")`.

If the wheel is not on PyPI, but nevertheless you believe there is nothing
preventing it (it is a Python package without C extensions):

- you can create the wheel yourself by running,
  ```py
  python -m pip install build
  python -m build
  ```
  from within the package folder where the `setup.py` are located. See the
  [Python packaging guide](https://packaging.python.org/tutorials/packaging-projects/#generating-distribution-archives)
  for more details. Then upload the wheel file somewhere (not to PyPI) and
  install it with micropip via its URL.
- please open an issue in the package repository asking the authors to upload
  the wheel.

If however the package has C extensions or its code requires patching, then
continue to the next steps.

```{note}
To determine if a package has C extensions, check if its `setup.py` contains
any compilation commands.
```

### 2. Creating the `meta.yaml` file

If your package is on PyPI, the easiest place to start is with the
{ref}`mkpkg tool <pyodide-mkpkg>`. From the Pyodide root directory, install the
tool with `pip install ./pyodide-build`, then run:

`python -m pyodide_build mkpkg <package-name>`

This will generate a `meta.yaml` file under `packages/<package-name>/` (see
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
exists, or by searching the [conda-forge GitHub
org](https://github.com/conda-forge/) for the package name.

The Pyodide `meta.yaml` file format was inspired by the one in conda, however it is
not strictly compatible.
```

### 3. Building the package and investigating issues

Once the `meta.yaml` file is ready, build the package with the following
commands from inside the package directory `packages/<package-name>`

```sh
python -m pyodide_build buildall --only 'package-name' packages dist
```

and see if there are any errors.

If there are errors you might need to

- patch the package by adding `.patch` files to `packages/<package-name>/patches`
- add the patch files to the `source/patches` field in the `meta.yaml` file

then restart the build.

If the build succeeds you can try to load the package by

1. Serve the dist directory with `python -m http.server`
2. Open `localhost:<port>/console.html` and try to import the package
3. You can test the package in the repl

#### Writing tests for your package

The tests should go in one or more files like
`packages/<package-name>/test_xxx.py`. Most packages have one test file named
`test_<package-name>.py`. The tests should look like:

```py
from pyodide_test_runner import run_in_pyodide

@run_in_pyodide(packages=["<package-name>"])
def test_mytestname(selenium):
  import <package-name>
  assert package.do_something() == 5
  # ...
```

If you want to run your package's full pytest test suite and your package
vendors tests you can do it like:

```py
from pyodide_test_runner import run_in_pyodide

@run_in_pyodide(packages=["<package-name>-tests", "pytest"])
def test_mytestname(selenium):
  import pytest
  pytest.main(["--pyargs", "<package-name>", "-k", "some_filter", ...])
```

you can put whatever command line arguments you would pass to `pytest` as
separate entries in the list.

#### Generating patches

If the package has a git repository, the easiest way to make a patch is usually:

1. Clone the git repository of the package. You might want to use the options
   `git clone --depth 1 --branch <version>`. Find the appropriate tag given the
   version of the package you are trying to modify.
2. Make a new branch with `git checkout -b pyodide-version` (e.g.,
   `pyodide-1.21.4`).
3. Make whatever changes you want. Commit them. Please split your changes up
   into focused commits. Write detailed commit messages! People will read them
   in the future, particularly when migrating patches or trying to decide if
   they are no longer needed. The first line of each commit message will also be
   used in the patch file name.
4. Use `git format-patch <version> -o <pyodide-root>/packages/<package-name>/patches/`
   to generate a patch file for your changes and store it directly into the
   patches folder.

#### Migrating Patches

When you want to upgrade the version of a package, you will need to migrate the
patches. To do this:

1. Clone the git repository of the package. You might want to use the options
   `git clone --depth 1 --branch <version-tag>`.
2. Make a new branch with `git checkout -b pyodide-old-version` (e.g.,
   `pyodide-1.21.4`).
3. Apply the current patches with `git am <pyodide-root>/packages/<package-name>/patches/*`.
4. Make a new branch `git checkout -b pyodide-new-version` (e.g.,
   `pyodide-1.22.0`)
5. Rebase the patches with `git rebase old-version --onto new-version` (e.g.,
   `git rebase pyodide-1.21.4 --onto pyodide-1.22.0`). Resolve any rebase
   conflicts. If a patch has been upstreamed, you can drop it with `git rebase --skip`.
6. Remove old patches with `rm <pyodide-root>/packages/<package-name>/patches/*`.
7. Use `git format-patch <version-tag> -o <pyodide-root>/packages/<package-name>/patches/`
   to generate new patch files.

#### Upstream your patches!

Please create PRs or issues to discuss with the package maintainers to try to
find ways to include your patches into the package. Many package maintainers are
very receptive to including Pyodide-related patches and they reduce future
maintenance work for us.

## The package build pipeline

Pyodide includes a toolchain to add new third-party Python libraries to the
build. We automate the following steps:

- If source is a url (not in-tree):
  - Download a source archive or a pure python wheel (usually from PyPI)
  - Confirm integrity of the package by comparing it to a checksum
  - If building from source (not from a wheel):
    - Apply patches, if any, to the source distribution
    - Add extra files, if any, to the source distribution
- If the source is not a wheel (building from a source archive or an in-tree
  source):
  - Run `build/script` if present
  - Modify the `PATH` to point to wrappers for `gfortran`, `gcc`, `g++`, `ar`,
    and `ld` that preempt compiler calls, rewrite the arguments, and pass them
    to the appropriate emscripten compiler tools.
  - Using `pypa/build`:
    - Create an isolated build environment. Install symbolic links from this
      isolated environment to "host" copies of certain unisolated packages.
    - Install the build dependencies requested in the package `build-requires`.
      (We ignore all version constraints on the unisolated packages, but version
      constraints on other packages are respected.
    - Run the PEP 517 build backend associated to the project to generate a wheel.
- Unpack the wheel with `python -m wheel unpack`.
- Run the `build/post` script in the unpacked wheel directory if it's present.
- Unvendor unit tests included in the installation folder to a separate zip file
  `<package name>-tests.zip`
- Repack the wheel with `python -m wheel pack`

Lastly, a `packages.json` file is created containing the dependency tree of all
packages, so {any}`pyodide.loadPackage` can load a package's dependencies
automatically.

#### Partial Rebuilds

By default, each time you run `buildpkg`, `pyodide-build` will delete the entire
source directory and replace it with a fresh copy from the download url. This is
to ensure build repeatability. For debugging purposes, this is likely to be
undesirable. If you want to try out a modified source tree, you can pass the
flag `--continue` and `buildpkg` will try to build from the existing source
tree. This can cause various issues, but if it works it is much more convenient.

Using the `--continue` flag, you can modify the sources in tree to fix the
build, then when it works, copy the modified sources into your checked out copy
of the package source repository and use `git format-patch` to generate the
patch.

## C library dependencies

Some Python packages depend on certain C libraries, e.g. `lxml` depends on
`libxml`.

To package a C library, create a directory in `packages/` for the C library. In
the directory, you should write `meta.yaml` that specifies metadata about the
library. See {ref}`meta-yaml-spec` for more details.

The minimal example of `meta.yaml` for a C library is:

```yaml
package:
  name: <name>
  version: <version>

source:
  url: <url>
  sha256: <sha256>

requirements:
  run:
    - <requirement>

build:
  library: true
  script: |
    emconfigure ./configure
    emmake make -j ${PYODIDE_JOBS:-3}
```

You can use the `meta.yaml` of other C libraries such as
[libxml](https://github.com/pyodide/pyodide/blob/main/packages/libxml/meta.yaml)
as a starting point.

After packaging a C library, it can be added as a dependency of a Python package
like a normal dependency. See `lxml` and `libxml` for an example (and also
`scipy` and `CLAPACK`).

_Remark:_ Certain C libraries come as emscripten ports, and do not have to be
built manually. They can be used by adding e.g. `-s USE_ZLIB` in the `cflags` of
the Python package. See e.g. `matplotlib` for an example. [The full list of
libraries with Emscripten ports is
here.](https://github.com/orgs/emscripten-ports/repositories?type=all)

## Structure of a Pyodide package

Pyodide is obtained by compiling CPython into WebAssembly. As such, it loads
packages the same way as CPython --- it looks for relevant files `.py` and `.so`
files in the directories in `sys.path`. When installing a package, our job is to
install our `.py` and `.so` files in the right location in emscripten's virtual
filesystem.

Wheels are just zip archives, and to install them we unzip them into the
`site-packages` directory. If there are any `.so` files, we also need to load
them at install time: WebAssembly must be loaded asynchronously, but Python
imports are synchronous so it is impossible to load `.so` files lazily.

```{eval-rst}
.. toctree::
   :hidden:

   meta-yaml.md
```
