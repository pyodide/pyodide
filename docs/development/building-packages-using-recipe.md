(building-packages-using-recipe)=

# Building Packages Using Recipe

While you can build Python packages from source,
we provide a `conda`-style recipe system to build multiple packages at once.

Using a recipe is also required to include the package in the Pyodide distribution.
See {ref}`adding-packages-into-pyodide-distribution` for more information.

## Building Packages from Recipe

### Creating the `meta.yaml` file

To build a Python package in tree, you need to create a `meta.yaml` file that
defines a recipe which includes build commands and patches (source code
edits), amongst other things.

If your package is on PyPI, the easiest place to start is with the
`pyodide skeleton pypi` command. Run

```bash
pyodide skeleton pypi <package-name>
```

This will generate a `meta.yaml` file under `packages/<package-name>/` (see
{ref}`meta-yaml-spec`). The `pyodide` cli tool will populate the latest version,
the download link and the sha256 hash by querying PyPI.

It doesn't currently handle package dependencies, so you will need to specify
those yourself in the `requirements` section of the `meta.yaml` file.

```yaml
requirements:
  host:
    # Dependencies that are needed to build the package
    - numpy
  run:
    # Dependencies that are needed to run the package
    - numpy
    - scikit-learn
```

```{note}
To determine build and runtime dependencies, including for non Python
libraries, it is often useful to check if the package was already built on
[conda-forge](https://conda-forge.org/) look at the corresponding `meta.yaml`
file. This can be done either by checking if the URL
`https://github.com/conda-forge/<package-name>-feedstock/blob/master/recipe/meta.yaml`
exists, or by searching the [conda-forge GitHub
org](https://github.com/conda-forge/) for the package name.

The Pyodide `meta.yaml` file format was inspired by the one in conda, however it is
not strictly compatible.
```

### Building the package

Once the `meta.yaml` file is ready, build the package with the following
command and see if there are any errors.
```sh
pyodide build-recipes <package-name> --install
```

This command will build the package and all its dependencies. The `--install`
The `--install` flag will install the built package into the `/dist` directory.

### Testing the package

If the build succeeds you can try to load the package in the Pyodide environment.

1. Visit Build Pyodide or download the latest release from the GitHub repository.
2. Copy everything built in the `/dist` directory to the downloaded Pyodide
   directory. This should include the `pyodide-lock.json` file and the
   wheel files that were built.
3. Serve the Pyodide directory with `python -m http.server --directory ./dist`.
4. Open `localhost:8000/console.html` and try to import the package.
5. You can test the package in the repl.

### Modifying Build Process

If you need to modify the build process (e.g. to fix build issues) you can do
this by modifying the `meta.yaml` file. The `build` section of the `meta.yaml`
is where you can run scripts, set environment variables, and add extra compile
and link flags.

```yaml
build:
  # You can add any shell scripts you want to run before invoking the build.
  # For instance, setting environment variables or downloading files, or modifying the source can be done here.
  script: |
    wget https://example.com/file.tar.gz
    export MY_ENV_VARIABLE=FOO
  # You can pass extra compile and link flags to the compiler by adding them here.
  cflags: |
    -O3
  cxxflags: |
    -O3
  ldflags: |
    -lm
  # This is the command that is passed to the build backend. For example, if you
  # need to pass extra flags to setuptools, you can pass them here.
  backend-flags: |
    setup-args=-Dallow-noblas=true
  # post is a script that is run after the build. This is useful for
  # post-processing the wheel file.
  post: |
    rm unnecessary-file-in-the-wheel.txt
```

### Patching the package source

If the package has a bug that needs to be fixed, you can apply `.patch` files
to the package source. This is commonly done when the package requires special handling
for Emscripten or Pyodide environment.

Place the patch files in the `patches` directory of the package, and specify
them in the `source.patches` section of the `meta.yaml` file. The patches will be
applied in the order they are listed. 

```yaml
source:
  patches:
    - patches/0001-Add-Wno-return-type-flag.patch
    - patches/0002-Align-xerbla_array-signature-with-scipy-expectation.patch
    - patches/0003-Skip-linktest.patch
```

(generating-patches)=

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
4. Use `git format-patch <version> -o packages/<package-name>/patches/`
   to generate a patch file for your changes and store it directly into the
   patches folder.

#### Upstream your patches!

Please create PRs or issues to discuss with the package maintainers to try to
find ways to include your patches into the package. Many package maintainers are
very receptive to including Pyodide-related patches and they reduce future
maintenance work for us.

### Upgrading a package

To upgrade a package's version to the latest one available on PyPI, do

```
pyodide skeleton pypi <package-name> --update
```

Because this does not handle package dependencies, you have to manually check
whether the `requirements` section of the `meta.yaml` file needs to be updated
for updated dependencies.

Upgrading a package's version may lead to new build issues that need to be resolved
(see above) and any patches need to be checked and potentially migrated (see below).

#### Migrating Patches

When you want to upgrade the version of a package, you will need to migrate the
patches. To do this:

1. Clone the git repository of the package. You might want to use the options
   `git clone --depth 1 --branch <version-tag>`.
2. Make a new branch with `git checkout -b pyodide-old-version` (e.g.,
   `pyodide-1.21.4`).
3. Apply the current patches with `git am packages/<package-name>/patches/*`.
4. Make a new branch `git checkout -b pyodide-new-version` (e.g.,
   `pyodide-1.22.0`)
5. Rebase the patches with `git rebase old-version --onto new-version` (e.g.,
   `git rebase pyodide-1.21.4 --onto pyodide-1.22.0`). Resolve any rebase
   conflicts. If a patch has been upstreamed, you can drop it with `git rebase --skip`.
6. Remove old patches with `rm packages/<package-name>/patches/*`.
7. Use `git format-patch <version-tag> -o packages/<package-name>/patches/`
   to generate new patch files.

### The package build pipeline

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
    - Run the {pep}`517` build backend associated to the project to generate a wheel.
- Unpack the wheel with `python -m wheel unpack`.
- Run the `build/post` script in the unpacked wheel directory if it's present.
- Unvendor unit tests included in the installation folder to a separate zip file
  `<package name>-tests.zip`
- Repack the wheel with `python -m wheel pack`

Lastly, a `pyodide-lock.json` file is created containing the dependency tree of all
packages, so {js:func}`pyodide.loadPackage` can load a package's dependencies
automatically.

### Partial Rebuilds

By default, each time you run `pyodide build-recipes`, it will delete the entire
source directory and replace it with a fresh copy from the download url. This is
to ensure build repeatability. For debugging purposes, this is likely to be
undesirable. If you want to try out a modified source tree, you can pass the
flag `--continue` and `build-recipes` will try to build from the existing source
tree. This can cause various issues, but if it works it is much more convenient.

Using the `--continue` flag, you can modify the sources in tree to fix the
build, then when it works, copy the modified sources into your checked out copy
of the package source repository and use `git format-patch` to generate the
patch.

### C library dependencies

Some Python packages depend on certain C libraries, e.g. `lxml` depends on
`libxml`.

To package a C library, create a directory for it and add `meta.yaml` file
similar to the one for Python packages. However, unlike the Python package, you
need to specify a build script that builds the C library.
See {ref}`meta-yaml-spec` for more details.

The minimal example of `meta.yaml` for a C library that uses `configure` and
`make` is:

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
  type: static_library
  script: |
    emconfigure ./configure
    emmake make
```

You can use the `meta.yaml` of other C libraries such as
[libxml](https://github.com/pyodide/pyodide-recipes/blob/main/packages/libxml/meta.yaml)
as a starting point.

After packaging a C library, it can be added as a dependency of a Python package
like a normal dependency. See `lxml` and `libxml` for an example (and also
`scipy` and `OpenBLAS`).

_Remark:_ Certain C libraries come as emscripten ports, and do not have to be
built manually. They can be used by adding e.g. `-s USE_ZLIB` in the `cflags` of
the Python package. See e.g. `matplotlib` for an example. [The full list of
libraries with Emscripten ports is
here.](https://github.com/orgs/emscripten-ports/repositories?type=all)

### Rust/PyO3 Packages

We currently build `cryptography` which is a Rust extension built with PyO3 and
`setuptools-rust`. It should be reasonably easy to build other Rust extensions.
If you want to build a package with Rust extension, you will need Rust >= 1.41,
and you need to set the rustup toolchain to `nightly`, and the target to
`wasm32-unknown-emscripten` in the build script
[as shown here](https://github.com/pyodide/pyodide-recipes/blob/main/packages/cryptography/meta.yaml),
but other than that there may be no other issues if you are lucky.

As mentioned [here](https://github.com/pyodide/pyodide/issues/2706#issuecomment-1154655224),
by default certain wasm-related `RUSTFLAGS` are set during `build.script`
and can be removed with `export RUSTFLAGS=""`.

If your project builds using maturin, you need to use maturin 0.14.14 or later. It is pretty easy to patch an existing project (see `projects/fastparquet/meta.yaml` for an example)
