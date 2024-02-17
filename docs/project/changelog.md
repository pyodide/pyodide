---
myst:
  substitutions:
    API: "<span class='badge badge-warning'>API Change</span>"
    Enhancement: "<span class='badge badge-info'>Enhancement</span>"
    Performance: "<span class='badge badge-info'>Performance</span>"
    Feature: "<span class='badge badge-success'>Feature</span>"
    Fix: "<span class='badge badge-danger'>Fix</span>"
    Update: "<span class='badge badge-success'>Update</span>"
    Breaking: "<span class='badge badge-danger'>BREAKING CHANGE</span>"
---

(changelog)=

# Change Log

## Unreleased

- Upgraded Python to v3.12.1
  {pr}`4431` {pr}`4435`

- Upgraded CoolProp to 6.6.0 {pr}`4397`.

- {{ Enhancement }} ABI Break: Updated Emscripten to version 3.1.52
  {pr}`4399`

- {{ Breaking }} `pyodide-build` entrypoint is removed in favor of `pyodide`.
  This entrypoint was deprecated since 0.22.0.
  {pr}`4368`

- {{ Enhancement }} Added apis to discard extra arguments when calling Python
  functions.
  {pr}`4392`

- {{ Breaking }} Pyodide will not fallback to `node-fetch` anymore when `fetch`
  is not available in the Node.js < 18 environment.
  {pr}`4417`

- {{ Enhancement }} Updated `pyimport` to support `pyimport("module.attribute")`.
  {pr}`4395`

- {{ Breaking }} The `--no-deps` option to `pyodide build-recipes` has been
  replaced with a separate subcommand `pyodide build-recipes-no-deps`.
  {pr}`4443`

- {{ Enhancement }} The `build/post` script now runs under the directory
  where the built wheel is unpacked.

### Packages

- New Packages: `cysignals`, `ppl`, `pplpy` {pr}`4407`, `flint`, `python-flint` {pr}`4410`,
  `memory_allocator` {pr}`4393`, `primesieve`, `primecount`, `primecountpy` {pr}`4477`,
  `pyxirr` {pr}`4513`

- Upgraded scikit-learn to 1.4.0 {pr}`4409`

- Upgraded `libproj` to 9.3.1, `pyproj` to 3.6.1, `h5py` to 3.10.0 {pr}`4426`,
  `packaging` to 23.2, `typing-extensions` to 4.9 {pr}`4428`, `bokeh` to 3.3.4 {pr}`4493`,
  `zengl` to 2.4.1 {pr}`4509`

- Upgraded `OpenBLAS` to 0.26 {pr}`4526`

## Version 0.25.0

_January 18, 2024_

### General

- {{ Enhancement }} ABI Break: Updated Emscripten to version 3.1.46
  {pr}`4359`

- {{ Breaking }} Node.js < 18 is no longer officially supported. Older versions
  of Node.js might still work, but they are not tested or guaranteed to work.
  {pr}`4269`

- {{ Enhancement }} Added experimental support for stack switching.
  {pr}`3957`, {pr}`3964`, {pr}`3987`, {pr}`3990`, {pr}`3210`

### JavaScript API

- {{ Fix }} `pyodide.setStdin` now does not consider an empty string as EOF.
  {pr}`4327`

- {{ Breaking }} `loadPyodide` does not accept `homedir` option anymore, use
  `env: {HOME: "/the/home/directory"}` instead. This have been deprecated since
  Pyodide 0.24.
  {pr}`4342`

- {{ Enhancement }} `pyodide.loadPackage` now returns an object with metadata
  about the loaded packages.
  {pr}`4306`

- {{ Fix }} Fixed default indexURL calculation in Node.js environment.
  {pr}`4288`

### Python API

- {{ Enhancement }} The `pyodide-py` package on `pypi` now includes `py.typed`
  markers so mypy will use the types.
  {pr}`4321`

- {{ Fix }} Fixed a bug that micropip would fail to install packages from
  pyodide-lock.json if the package's name differs from its normalized name.
  {pr}`4319`

- {{ Enhancement }} Added a no-op `WebLoop.close` method so that attempts to
  close the event loop will not raise an exception.
  {pr}`4329`

### Python / JavaScript Foreign Function Interface

- {{ Fix }} `jsarray.pop` now works correctly. It previously returned the wrong
  value and leaked memory.
  {pr}`4236`

- {{ Breaking }} `PyProxy.toString` now calls `str` instead of `repr`. For now
  you can opt into the old behavior by passing `pyproxyToStringRepr: true` to
  `loadPyodide`, but this may be removed in the future.
  {pr}`4247`

- {{ Fix }} when accessing a `JsProxy` attribute invokes a getter and the getter
  throws an error, that error is propagated instead of being turned into an
  `AttributeError`.
  {pr}`4254`

- {{ Fix }} `import type { PyProxy } from "pyodide/ffi"` now works with the
  `NodeNext` typescript target.
  {pr}`4256`

- {{ Fix }} Fixed a bug that occurs when using `toJs` with both `dictConverter`
  and `defaultConverter` arguments.
  {pr}`4263`

- {{ Enhancement }} Added `JsArray.remove` and `JsArray.insert` methods.
  {pr}`4326`

- {{ Breaking }} Type exports of `PyProxy` subtypes have been moved from
  `pyodide` to `pyodide/ffi` and many of them have changed names.
  {pr}`4342`

- {{ Breaking }} The methods for checking `PyProxy` capabilities (e.g.,
  `supportsHas`, `isCallable`) are now removed. Use e.g.,
  `instanceof pyodide.ffi.PyCallable` instead.
  {pr}`4342`

### Pyodide CLI

- {{ Enhancement }} `pyodide config` command now show additional config
  variables: `rustflags`, `cmake_toolchain_file`, `pyo3_config_file`,
  `rust_toolchain`, `cflags` `cxxflags`, `ldflags`, `meson_cross_file`. These
  variables can be used in out-of-tree build to set the same variables as
  in-tree build.
  {pr}`4241`

- {{ Enhancement }} `pyodide build` command now accepts `--config-setting`
  (`-C`) option to pass flags to the build backend, just like `python -m build`
  command.
  {pr}`4308`

### Load time & size optimizations

- {{ Performance }} Do not use `importlib.metadata` when identifying installed
  packages, which reduces the time to load Pyodide.
  {pr}`4147`

### Build system

- {{ Fix }} Fixed `Emscripten.cmake` not vendored in pyodide-build since 0.24.0.
  {pr}`4223`

- {{ Fix }} pyodide-build now does not override `CMAKE_CONFIG_FILE` and
  `PYO3_CONFIG_FILE` env variables if provided by user.
  {pr}`4223`

- {{ Fix }} Fixed a bug that webpack messes up dynamic import of `pyodide.asm.js`.
  {pr}`4294`

### Packages

- New Packages: `river` {pr}`4197`, `sisl` {pr}`4210`, `frozenlist` {pr}`4231`,
  `zengl` {pr}`4208`, `msgspec` {pr}`4265`, `aiohttp` {pr}`4282`, `pysam` {pr}`4268`,
  `requests`, `urllib3` {pr}`4332`, `nh3` {pr}`4387`
- Upgraded zengl to 2.2.0 {pr}`4364`

## Version 0.24.1

_September 25, 2023_

- {{ Fix }} Fixed `LONG_BIT definition appears wrong for platform` error happened in out-of-tree build.
  {pr}`4136`

- {{ Fix }} Fixed an Emscripten bug that broke some matplotlib functionality.
  {pr}`4163`

- {{ Fix }} `pyodide.checkInterrupt` works when there is no interrupt buffer and
  the gil is not held.
  {pr}`4164`

### Packages

- Upgraded scipy to 1.11.2 {pr}`4156`
- Upgraded sourmash to 4.8.4 {pr}`4154`
- Upgraded scikit-learn to 1.3.1 {pr}`4161`
- Upgraded micropip to 0.5.0 {pr}`4167`

## Version 0.24.0

_September 13, 2023_

### General

- {{ Update }} Pyodide now runs Python 3.11.3.
  {pr}`3741`

- {{ Enhancement }} ABI Break: Updated Emscripten to version 3.1.45 {pr}`3665`,
  {pr}`3659`, {pr}`3822`, {pr}`3889`, {pr}`3890`, {pr}`3888`, {pr}`4055`,
  {pr}`4056`, {pr}`4073`, {pr}`4094`

### JavaScript API

- {{ Performance }} Added a `packages` optional argument to `loadPyodide`.
  Passing packages here saves time by downloading them during the Pyodide
  bootstrap.
  {pr}`4100`

- {{ Enhancement }} `runPython` and `runPythonAsync` now accept a `filename`
  optional argument which is passed as the `filename` argument to `eval_code`
  (resp. `eval_code_async`). Also, if a `filename` is passed to `eval_code`
  which does not start with `<` and end with `>`, Pyodide now uses the
  `linecache` module to ensure that source lines can appear in tracebacks.
  {pr}`3993`

- {{ Performance }} For performance reasons, don't render extra information in
  PyProxy destroyed message by default. By using `pyodide.setDebug(true)`, you
  can opt into worse performance and better error messages.
  {pr}`4027`

- {{ Enhancement }} It is now possible to pass environment variables to
  `loadPyodide` via the `env` argument. `homedir` is deprecated in favor of
  `{env: {HOME: whatever_directory}}`.
  {pr}`3870`

- {{ Enhancement }} The `setStdin`, `setStdout` and `setStderr` APIs have been
  improved with extra control and better performance.
  {pr}`4035`

### Python API

- {{ Enhancement }} Added `headers` property to `pyodide.http.FetchResponse`.
  {pr}`2078`

- {{ Enhancement }} Added `FetchResponse.text()` as a synonym to
  `FetchResponse.string()` for better compatibility with other requests APIs.
  {pr}`4052`

- {{ Breaking }} Changed the `FetchResponse` body getter methods to no longer
  throw an `OSError` exception for 400 and above response status codes. Added
  `FetchResponse.raise_for_status` to raise an `OSError` for error status codes.
  {pr}`3986` {pr}`4053`

### Python / JavaScript Foreign Function Interface

- {{ Performance }} Improved performance of PyProxy creation.
  {pr}`4096`

- {{ Fix }} Fixed adding getters/setters to a `PyProxy` with
  `Object.defineProperty` and improved compliance with JavaScript rules around
  Proxy traps.
  {pr}`4033`

- {{ Enhancement }} The promise methods `then`, `catch` and `finally_` are now
  present also on `Task`s as well as `Future`s.
  {pr}`3748`

- {{ Enhancement }} Added methods to a `PyProxy` of a `list` to make these work
  as drop-in replacements for JavaScript Arrays.
  {pr}`3853`

- {{ Enhancement }} When a `JsProxy` of an array is passed to Python builtin
  functions that use the `PySequence_*` APIs, it now works as expected. Also
  `jsarray * n` repeats the array `n` times and `jsarray + iterable` returns a
  new array with the result values from the iterable appended.
  {pr}`3904`

### Deployment

- {{ API }} Changed the name of the default lockfile from `repodata.json` to
  `pyodide-lock.json`
  {pr}`3824`

### Build System

- {{ Update }} The docker image now has node v20 instead of node v14.
  {pr}`3819`

- {{ Enhancement }} Added `check_wasm_magic_number` function to validate `.so`
  files for WebAssembly (WASM) compatibility.
  {pr}`4018`

- {{ Enhancement }} In pyodide build, automatically skip building package
  dependencies that are already included in the pyodide distribution.
  {pr}`4058`

### Packages

- New packages: sourmash {pr}`3635`, screed {pr}`3635`, bitstring {pr}`3635`,
  deprecation {pr}`3635`, cachetools {pr}`3635`, xyzservices {pr}`3786`,
  simplejson {pr}`3801`, protobuf {pr}`3813`, peewee {pr}`3897`, Cartopy
  {pr}`3909`, pyshp {pr}`3909`, netCDF4 {pr}`3910`, igraph {pr}`3991`, CoolProp
  {pr}`4028`, contourpy {pr}`4102`, awkward-cpp {pr}`4101`, orjson {pr}`4036`.

- Upgraded numpy to 1.25.2 {pr}`4125`

- Upgraded scipy to 1.11.1 {pr}`3794`, {pr}`3996`

- OpenBLAS has been added and scipy now uses OpenBLAS rather than CLAPACK
  {pr}`3331`.

### Pyodide CLI

- {{ Enhancement }} `pyodide build-recipes` now accepts a `--metadata-files`
  option to install `*.whl.metadata` files as specified in
  [PEP 658](https://peps.python.org/pep-0658/).
  {pr}`3981`

### Misc

- {{ Enhancement }} Add an example for `loadPyodide` and `pyodide.runPython
{pr}`4012`, {pr}`4011`

## Version 0.23.4

_July 6, 2023_

- {{ Enhancement }} The environment variable `PYODIDE_BUILD_EXPORTS` can now be
  used instead of the `--exports` argument to `pyodide build` to specify `.so`
  file exports of packages.
  {pr}`3973`

- {{ Fix }} Pin `pydantic` to `<2`.
  {pr}`3971`

- {{ Enhancement }} Allow customizing cache location for packages when running in Node
  {pr}`3967`

- {{ Enhancement }} Re-enabled sparseqr, freesasa, lightgbm, opencv-python, and wordcloud
  {pr}`3783`, {pr}`3970`

- {{ Fix }} A `JSProxy` of a `DOMException` will now inherit from exception so
  it can be raised in Python.
  {pr}`3868`

- {{ Fix }} The feature detection for `JSProxy` has been improved so that it
  should never fail even when handling strange or ill-behaved JavaScript proxy
  objects.
  {pr}`3740`, {pr}`3750`

- {{ Fix }} A `PyProxy` of a callable is now an `instanceof Function`. (If you
  are trying to feature detect whether something is callable or not in
  JavaScript, the correct way is to use `typeof o === "function"`. But you may
  have dependencies that don't do this correctly.)
  {pr}`3925`

- {{ Fix }} `from jsmodule import *` now works.
  {pr}`3903`

## Version 0.23.3

_June 17, 2023_

- {{ Fix }} `getattr(jsproxy, 'python_reserved_word')` works as expected again
  (as well as `hasattr` and `setattr`). This fixes a regression introduced in
  {pr}`3617`.
  {pr}`3926`

- {{ Fix }} `pyodide build` now replaces native `.so` slugs with Emscripten
  slugs. Usually `.so`s in the generated wheels are actually Emscripten `.so`s
  so this is good. If they are actually native `.so`s then there is a problem
  either way.
  {pr}`3903`

## Version 0.23.2

_May 2, 2023_

- {{ Enhancement }} Changed the name of the `--output-directory` argument to
  `pyodide build` to `--outdir` to match pypa/build. `--output-directory` is
  still accepted for backwards compatibility.
  {pr}`3811`

## Version 0.23.1

_April 13, 2023_

### Deployment

- {{ Fix }} Export `python_stdlib.zip` in `package.json`.
  {pr}`3723`

### CLI

- {{ Enhancement }} `pyodide build` now accepts an `--output-directory` argument.
  {pr}`3746`

- {{ Fix }} Fix `pyodide py-compile` not to ignore the `--compression-level`
  option when applied on a single file.
  {pr}`3727`

- {{ Fix }} Fix an issue where the `pyodide venv` command did not work correctly in pyodide-build
  version 0.23.0 because of missing `python_stdlib.zip`.
  {pr}`3760`

- {{ Fix }} `python -m pip` works correctly in the Pyodide venv now.
  {pr}`3761`

- {{ Fix }} Executables installed in a Pyodide virtual environment now run in
  Pyodide not in the host Python.
  {pr}`3752`

### Build System

- {{ Fix }} Fix `PYODIDE_ROOT` to point the correct directory when running out-of-tree build.
  {pr}`3751`

## Version 0.23.0

_March 30, 2023_

### General

- {{ Update }} Pyodide now runs Python 3.11.2 which officially supports
  WebAssembly as a [PEP11 Tier 3](https://peps.python.org/pep-0011/#tier-3) platform.
  {pr}`3252`, {pr}`3614`

- {{ Update }} We now build libpyodide.a so the Pyodide foreign function
  interface can be experimentally linked into other Emscripten builds of Python.
  {pr}`3335`

- {{ Enhancement }} Updated Emscripten to version 3.1.32
  {pr}`3471`, {pr}`3517`, {pr}`3599`

### JavaScript API

- {{ Breaking }} Type exports of `PyProxy` subtypes have been moved from
  `pyodide` to `pyodide/ffi` and many of them have changed names. The original
  exports are still available but they are deprecated.
  {pr}`3523`

- {{ Breaking }} The methods for checking `PyProxy` capabilities (e.g.,
  `supportsHas`, `isCallable`) are now deprecated. Use e.g.,
  `instanceof pyodide.ffi.PyCallable` instead.
  {pr}`3523`

- {{ Enhancement }} Added subclasses of `PyProxy` for each mixin. These can be
  used to check whether a `PyProxy` supports a given set of methods with
  `instanceof` e.g., `x instanceof pyodide.ffi.PyDict`.
  {pr}`3523`

- {{ Enhancement }} Added `stdLibURL` parameter to `loadPyodide` allowing to customize
  the URL from which the Python standard library is loaded.
  {pr}`3670`

- {{ Enhancement }} Checking whether an object is an instance of a `PyProxy` now
  only recognizes a `PyProxy` generated from the same Python interpreter. This
  means that creating multiple interpreters and importing a `PyProxy` from one
  into another no longer causes a fatal error.
  {pr}`3545`

- {{ Enhancement }} `as_object_map` now accepts a keyword argument `hereditary`.
  If set to `True` and indexing the object returns a plain-old-object, then the
  return value will be automatically mapped in `as_object_map` as well.
  {pr}`3638`

- {{ Enhancement }} A `JsProxy` of a JavaScript error object can be directly
  thrown as Python exceptions. Previously Pyodide automatically wrapped them in
  a `JsException` but that is no longer needed -- now `JsException` inherits
  from both `JsProxy` and `Exception`.
  {pr}`3455`

- {{ Enhancement }} `runPython` and `runPythonAsync` now accept a `locals`
  argument.
  {pr}`3618`

- {{ Fix }} Calling `loadPyodide` repeatedly in Node no longer results in
  `MaxListenersExceededWarning`. Also, calling `loadPyodide` in Node v14 no
  longer changes unhandled rejections in promises.
  {pr}`3542`

- {{ Fix }} If the `locals` argument to `eval_code` or `eval_code_async` is
  `None` it now uses `locals=globals` as the documentation says.
  {pr}`3580`

### Python standard library

- {{ Breaking }} Unvendored `_pydecimal` and `pydoc_data` from the standard
  library. Now these modules need to be loaded with `pyodide.loadPackage` or
  `micropip.install`, or auto-loaded via imports in `pyodide.runPythonAsync`
  {pr}`3525`

- {{ Breaking }} Test files of stdlib `ctypes` and `unittest` are now moved to
  `test/ctypes` and `test/unittest` respectively. This change is adapted from
  [CPython 3.12](https://github.com/python/cpython/issues/93839).
  {pr}`3507`

### Deployment

- {{ Breaking }} Pyodide no longer uses Emscripten preload plugin, hence
  `pyodide.asm.data` is removed, in favor of `python_stdlib.zip`. This change
  normally shouldn't affect users, but if you were using this file in a
  bundler, you will need to remove it. {pr}`3584`

- {{ Breaking }} `pyodide_py.tar` file is removed. This change normally
  shouldn't affect users, but if you were using this file in a bundler,
  you will need to remove it.
  {pr}`3621`

- {{ Breaking }} Python standard libraries are now vendored in a zipfile:
  `/lib/python{version}.zip` in the in-browser MEMFS file system. If you need
  to access the standard library source code, you need to unpack the zip file.
  For example:
  `import shutil; shutil.unpack_archive('/lib/python311.zip', '/lib/python3.11', 'zip)`
  {pr}`3584`

- {{ Fix }} Improves the compression of wheel files with the JsDelivr CDN. For
  browsers that support the Brotli compression (most modern ones) this should
  result in a size reduction of 20-30%. Also most many `pyodide` CLI
  sub-commands now support `--compression-level` as an optional parameter.
  {pr}`3655`

- {{ Breaking }} Following libraries are now not linked to the Pyodide main module:
  `libgl`, `libal`, `libhtml5`. This normally shouldn't affect users, but if you
  are using these libraries in a package that are built out-of-tree, you will
  need to link them to the package manually.
  {pr}`3505`

### Python / JavaScript Foreign Function Interface

- {{ Fix }} PyProxies of Async iterators are now async iterable JavaScript
  objects. The code:

  ```javascript
  for await (let x of async_iterator_pyproxy) {
    // ...
  }
  ```

  would previously fail with `TypeError: async_iterator_pyproxy is not async
iterable`. (Python async _iterables_ that were not also iterators were already
  async iterable, the problem was only with Python objects that are both async
  _iterable_ and an async iterator.)
  {pr}`3708`

- {{ Enhancement }} A py-compiled build which has smaller and faster-to-load
  packages is now deployed under
  `https://cdn.jsdelivr.net/pyodide/v0.23.0/pyc/` (also for future
  versions). The exceptions obtained with this builds will not include code
  snippets however. {pr}`3701`

- {{ Breaking }} Removed support for calling functions from the root of `pyodide` package
  directly. This has been deprecated since v0.21.0. Now all functions are only available
  under submodules.
  {pr}`3677`

- {{ Breaking }} Removed support for passing the "message" argument to `PyProxy.destroy`
  in a positional argument. This has been deprecated since v0.22.0.
  {pr}`3677`

- {{ Enhancement }} Python does not allow reserved words to be used as attributes.
  For instance, `Array.from` is a `SyntaxError`. (JavaScript has a more robust
  parser which can handle this.) To handle this, if an attribute to a `JsProxy`
  consists of a Python reserved word followed by one or more underscores, we remove
  a single underscore from the end of the attribute. For instance, `Array.from_`
  would access `from` on the underlying JavaScript object, whereas `o.from__`
  accesses the `from_` attribute.
  {pr}`3617`

### Build System

- {{ Breaking }} When building meta-packages (`core` and `min-scipy-stack`),
  you must prefix `tag:` to the meta-package name. For example, to build the
  `core` meta-package, you must run `pyodide build-recipes tag:core`, or
  `PYODIDE_PACKAGES="tag:core" make`.
  {pr}`3444`

- {{ Enhancement}} Add `--build-dependencies` to `pyodide build` command
  to fetch and build dependencies of a package being built.
  Also adds `--skip-dependency` to ignore selected dependencies.
  {pr}`3310`

- {{ Enhancement}} Added `pyodide build` support for building a list of packages
  from a requirements.txt file with `pyodide build -r <requirements.txt>`. Also
  can output a list of chosen dependencies in the same format when building a
  package and dependencies using the `--output-lockfile <lockfile.txt>`
  argument. This enables repeatable builds of packages.
  {pr}`3469`

- {{ Enhancement }} Added `package/tag` key to the `meta.yaml` spec to group
  packages.
  {pr}`3444`

- {{ Enhancement }} `pyodide build-recipes` now autodetects the number of
  CPU cores in the system and uses them for parallel builds.
  {pr}`3559` {pr}`3598`

- {{ Fix }} Fixed pip install error when installing cross build environment.
  {pr}`3562`

- {{ Enhancement }} Response files are now correctly handled when
  calculating exported symbols.
  {pr}`3645`

- {{ Fix }} Fix occasional build failure when building rust packages.
  {pr}`3607`

- {{ Enhancement }} Improved logging in `pyodide-build` with rich.
  {pr}`3442`

- {{ Enhancement }} `pyodide build-recipes` now accepts `--no-deps` parameter, which skips
  building dependencies of the package. This replaces `pyodide-build buildpkg`.
  {pr}`3520`

- {{ Enhancement }} `pyodide build-recipes` now works out-of-tree.

### Pyodide CLI

- {{ Breaking }} Removed deprecated CLI entrypoints `pyodide-build buildall` which is
  replaced by `pyodide build-recipes`, and `pyodide-build mkpkg` which is
  replaced by `pyodide skeleton pypi` {pr}`3668`.

- {{ Feature }} Added `pyodide py-compile` CLI command that py compiles a wheel or a zip
  file, converting .py files to .pyc files. It can also be applied to a folder
  with wheels / zip files. If the input folder contains the
  `repodata.json` the paths and checksums it contains will also be updated
  {pr}`3253` {pr}`3700`

- {{ Feature }} Added `pyodide create-zipfile` CLI command that creates a zip file of a
  directory. This command is hidden by default since it is not intended for use
  by end users.
  {pr}`3411` {pr}`3463`

### REPL

- {{ Fix }} Non-breaking space characters are now automatically converted to
  regular spaces in pyodide REPL.
  {pr}`3558`

- {{ Enhancement }} Allow changing the build type used in the REPL by passing the
  `build` argument to the REPL URL. For instance,
  `https://pyodide.org/en/latest/console.html?build=debug` will load debug dev build.
  {pr}`3671`

### Packages

- New packages: fastparquet {pr}`3590`, cramjam {pr}`3590`, pynacl {pr}`3500`,
  pyxel {pr}`3508`.
  mypy {pr}`3504`, multidict {pr}`3581`, yarl {pr}`3702`, idna {pr}`3702`,
  cbor-diag {pr}`3581`.

- Upgraded to micropip 0.3.0 (see
  [changelog](https://github.com/pyodide/micropip/blob/main/CHANGELOG.md)
  {pr}`3709`

- Added experimental [support for SDL based packages](using-sdl) {pr}`3508`

- Upgraded packages: see the list of packages versions in this release in
  {ref}`packages-in-pyodide`.

### List of Contributors

Alexey Ignatiev, Andrea Giammarchi, Arpit, Christian Clauss, Deepak Cherian,
Eli Lamb, Feodor Fitsner, Gyeongjae Choi, Hood Chatham, Jeff Glass, Jo Bovy,
Joe Marshall, josephrocca, Loïc Estève, martinRenou, messense, Nicholas
Bollweg, Roman Yurchak, TheOnlyWayUp, Victor Blomqvist, Ye Joo Park

## Version 0.22.1

_January 25, 2023_

- {{ Breaking }} `setStdin` now accepts an extra `autoEOF` parameter. If `true`,
  it will insert an EOF automatically after each string or buffer. Defaults to
  `true`. This also affects the behavior of the `stdin` argument to
  `loadPyodide`.
  {pr}`3488`

- {{ Fix }} `from pyodide.ffi import *` doesn't raise an `ImportError` anymore.
  {pr}`3484`

- {{ Enhancement }} Pyodide displays a better message when someone calls posix
  `exit` or `os._exit`.
  {pr}`3496`

### Package Loading

- {{ Fix }} Fix incorrect error message when loading a package
  include in Pyodide fails.
  {pr}`3435`

### Build system

- {{ Fix }} Emscripten is no longer required to create a Pyodide virtual
  environment.
  {pr}`3485`

- {{ Fix }} Fixed a bug where `pyodide build` would fail on package that use
  CMake, when run multiple times.
  {pr}`3445`

- {{ Fix }} pyodide build: Don't pass the directory to the build backend args,
  only pass the arguments.
  {pr}`3490`

- {{ Fix }} `pyodide config` won't print extra messages anymore.
  {pr}`3483`

- {{ Fix }} Pass the same environment variables for out of tree builds as for in
  tree builds.
  {pr}`3495`

## Version 0.22.0

_January 3, 2023_

[See the release notes for a summary.](https://blog.pyodide.org/posts/0.22-release/)

### Deployment and testing

- {{ Breaking }} `pyodide-cdn2.iodide.io` is not available anymore. Please use
  `https://cdn.jsdelivr.net/pyodide` instead.
  {pr}`3150`.

- {{ Breaking }} We don't publish pre-built Pyodide docker images anymore. Note
  that `./run_docker --pre-built` was not working for a while and it was
  actually equivalent to `./run_docker`. If you need to build a single Python
  wheel out of tree, you can use the `pyodide build` command instead. See
  [our blog post](https://blog.pyodide.org/posts/0.21-release/#building-binary-wheels-for-pyodide)
  for more information.
  {pr}`3342`.

- {{ Enhancement }} The releases are now called `pyodide-{version}.tar.gz`
  rather than `pyodide-build-{version}.tar.gz`
  {pr}`2996`

- {{ Enhancement }} Added a new release file called
  `pyodide-core-{version}.tar.gz` intended for use in Node. It contains the
  files needed to start Pyodide and no additional packages.
  {pr}`2999`

- {{ Enhancement }} The full test suite is now run in Safari
  {pr}`2578`, {pr}`3095`.

- {{ Enhancement }} Added Gitpod configuration to the repository.
  {pr}`3201`

### Foreign function interface

#### JsProxy / JavaScript from Python

- {{ Enhancement }} Implemented `reverse`, `__reversed__`, `count`, `index`,
  `append`, and `pop` for `JsProxy` of Javascript arrays so that they implement
  the `collections.abc.MutableSequence` API.
  {pr}`2970`

- {{ Enhancement }} Implemented methods `keys`, `items`, `values`, `get`, `pop`,
  `setdefault`, `popitem`, `update`, and `clear` for `JsProxy` of map-like
  objects so that they implement the `collections.abc.MutableMapping` API.
  {pr}`3275`

- {{ Enhancement }} It's now possible to destructure a JavaScript array, map, or
  object returned by `as_object_map` with a `match` statement.
  {pr}`2906`

- {{ Enhancement }} Added `then`, `catch`, and `finally_` methods to the
  `Future`s used by Pyodide's event loop so they can be used like `Promise`s.
  {pr}`2997`

- {{ Enhancement }} `create_proxy` now takes an optional `roundtrip` parameter.
  If this is set to `True`, then when the proxy is converted back to Python, it
  is converted back to the same double proxy. This allows the proxy to be
  destroyed from Python even if no reference is retained.
  {pr}`3163`, {pr}`3369`

- {{ Enhancement }} A `JsProxy` of a function now has a `__get__` descriptor
  method, so it's possible to use a JavaScript function as a Python method. When
  the method is called, `this` will be a `PyProxy` pointing to the Python object
  the method is called on.
  {pr}`3130`

- {{ Enhancement }} A `JsProxy` now has an `as_object_map` method. This will
  treat the object as a mapping over its `ownKeys` so for instance:
  `run_js("({a:2, b:3})").as_object_map()["a"]` will return 2. These implement
  `collections.abc.MutableMapping`.
  {pr}`3273`, {pr}`3295`, {pr}`3297`

- {{ Enhancement }} Split up the `JsProxy` documentation class into several
  classes, e.g., `JsBuffer`, `JsPromise`, etc. Implemented `issubclass` and
  `isinstance` on the various synthetic and real `JsProxy` classes so that they
  behave the way one might naively expect them to (or at least closer to that
  than it was before).
  {pr}`3277`

- {{ Enhancement }} Added type parameters to many of the `JsProxy` subtypes.
  {pr}`3387`

- {{ Enhancement }} Added `JsGenerator` and `JsIterator` types to `pyodide.ffi`.
  Added `send` method to `JsIterator`s and `throw`, and `close` methods to
  `JsGenerator`s.
  {pr}`3294`

- {{ Enhancement }} It is now possible to use asynchronous JavaScript iterables,
  iterators and generators from Python. This includes support for `aiter` for
  async interables, `anext` and `asend` for async iterators, and `athrow` and
  `aclose` for async generators.
  {pr}`3285`, {pr}`3299`, {pr}`3339`

- {{ Enhancement }} JavaScript generators and async generators that are created
  from Python now are wrapped so that Python objects sent to them as arguments
  or from `.send` / `.asend` are kept alive until the generator is exhausted or
  `.close`d. This makes generators significantly more ergonomic to use, at the
  cost of making memory leaks more likely if the generator is never finalized.
  {pr}`3317`

- {{ Enhancement }} Added a mypy typeshed for some common functionality for the
  `js` module.
  {pr}`3298`

- {{ Enhancement }} mypy understands the types of more things now.
  {pr}`3385`

- {{ Fix }} Fixed bug in `split` argument of `pyodide.console.repr_shorten`.
  Added `shorten` function.
  {pr}`3178`

#### PyProxy / Using Python from JavaScript

- {{ Enhancement }} Added a type field to `PythonError` (e.g., a StopIteration
  error would have `e.type === "StopIteration"`)
  {pr}`3289`

- {{ Enhancement }} It is now possible to use asynchronous Python generators
  from JavaScript.
  {pr}`3290`

- {{ Enhancement }} PyProxies of synchronous and asynchronous Python generators
  now support `return` and `throw` APIs that behave like the ones on JavaScript
  generators.
  {pr}`3346`

- {{ Enhancement }} It is possible to make a `PyProxy` that takes `this` as the
  first argument using the `PyProxy.captureThis` method. The `create_proxy`
  method also has a `capture_this` argument which causes the `PyProxy` to
  receive `this` as the first argument if set to `True`
  {pr}`3103`, {pr}`3145`

### JavaScript API

- {{ Enhancement }} Users can do a static import of `pyodide/pyodide.asm.js` to
  avoid issues with dynamic imports. This allows the use of Pyodide with
  module-type service workers.
  {pr}`3070`

- {{ Enhancement }} Added a new API `pyodide.mountNativeFS` which mounts a
  {js:class}`FileSystemDirectoryHandle` into the Pyodide file system.
  {pr}`2987`

- {{ Enhancement }} `loadPyodide` has a new option called `args`. This list will
  be passed as command line arguments to the Python interpreter at start up.
  {pr}`3021`, {pr}`3282`

- Removed "Python initialization complete" message printed when loading is
  finished.
  {pr}`3247

- {{ Breaking }} The messageCallback and errorCallback argument to `loadPackage`
  and `loadPackagesFromImports` is now passed as named arguments. The old usage
  still works with a deprecation warning.
  {pr}`3149`

- {{ Enhancement }} `loadPackage` and `loadPackagesFromImports` now accepts a
  new option `checkIntegrity`. If set to False, integrity check for Python
  Packages will be disabled.

- {{ Enhancement }} Added APIs `pyodide.setStdin`, `pyodide.setStdout`,
  `pyodide.setStderr` for changing the stream handlers after loading Pyodide.
  Also added more careful control over whether `isatty` returns true or false on
  stdin, stdout, and stderr.
  {pr}`3268`

### Package Loading

- {{ Enhancement }} Pyodide now shows more helpful error messages when importing
  packages that are included in Pyodide fails.
  {pr}`3137`, {pr}`3263`

- {{ Fix }} Shared libraries with version suffixes are now handled correctly.
  {pr}`3154`

- {{ Breaking }} Unvendored the sqlite3 module from the standard library. Before
  `sqlite3` was included by default. Now it needs to be loaded with
  `pyodide.loadPackage` or `micropip.install`.
  {pr}`2946`

- {{ Breaking }} The Pyodide Python package is installed into `/lib/python3.10`
  rather than `/lib/python3.10/site-packages`.
  {pr}`3022`

- {{ Breaking }} The matplotlib HTML5 backends are now available as part of the
  [`matplotlib-pyodide`](https://github.com/pyodide/matplotlib-pyodide) package.
  If you use the default backend from Pyodide, no changes are necessary.
  However, if you previously specified the backend with `matplotlib.use`, the
  URL is now different. See [package
  readme](https://github.com/pyodide/matplotlib-pyodide) for more details.
  {pr}`3061`

- {{ Breaking }} The micropip package was moved to a separate repository
  [pyodide/micropip](https://github.com/pyodide/micropip). In addion to
  installing the version shipped with a given Pyodide release, you can also
  install a different micropip version from
  [PyPi](https://pypi.org/project/micropip/) with,

  ```
  await pyodide.loadPackage('packaging')
  await pyodide.loadPackage('<URL of the micropip wheel on PyPI>')
  ```

  from Javascript. From Python you can import the Javascript Pyodide package,

  ```
  import pyodide_js
  ```

  and call the same functions as above.
  {pr}`3122`

- {{ Enhancement }} The parsing and validation of `meta.yaml` according to the
  specification is now done more rigorously with Pydantic.
  {pr}`3079`

- {{ Breaking }} The `source/md5` checksum field is not longer supported in
  `meta.yaml` files, use `source/sha256` instead
  {pr}`3079`

- {{ Breaking }} `pyodide_build.io.parse_package_config` function is removed in
  favor of `pyodide_build.MetaConfig.from_yaml`
  {pr}`3079`

- {{ Fix }} `ctypes.util.find_library` will now search WASM modules from
  LD_LIBRARY_PATH.
  {pr}`3353`

### Build System

- {{ Enhancement }} Updated Emscripten to version 3.1.27
  {pr}`2958`, {pr}`2950`, {pr}`3027`, {pr}`3107`, {pr}`3148`, {pr}`3236`,
  {pr}`3239`, {pr}`3280`, {pr}`3314`

- {{ Enhancement }} Added `requirements/host` key to the `meta.yaml` spec to
  allow host dependencies that are required for building packages.
  {pr}`2132`

- {{ Enhancement }} Added `package/top-level` key to the `meta.yaml` spec to
  calculate top-level import names for the package. Previously `test/imports`
  key was used for this purpose.
  {pr}`3006`

- {{ Enhancement }} Added `build/vendor-sharedlib` key to the `meta.yaml` spec
  which vendors shared libraries into the wheel after building.
  {pr}`3234` {pr}`3264`

- {{ Enhancement }} Added `build/type` key to the `meta.yaml` spec which
  specifies the type of the package.
  {pr}`3238`

- {{ Enhancement }} Added `requirements/executable` key to the `meta.yaml` spec
  which specifies the list of executables required for building a package.
  {pr}`3300`

- {{ Breaking }} `build/library` and `build/sharedlibrary` key in the
  `meta.yaml` spec are removed. Use `build/type` instead.
  {pr}`3238`

- {{ Fix }} Fixed a bug that `backend-flags` propagated to dependencies.
  {pr}`3153`

- {{ Fix }} Fixed a bug that shared libraries are not copied into distribution
  directory when it is already built.
  {pr}`3212`

- {{ Enhancement }} Added a system for making Pyodide virtual environments. This
  is for testing out of tree builds. For more information, see [the
  documentation](building-and-testing-packages-out-of-tree).
  {pr}`2976`, {pr}`3039`, {pr}`3040`, {pr}`3044`, {pr}`3096`, {pr}`3098`,
  {pr}`3108`, {pr}`3109`, {pr}`3241`

- Added a new CLI command `pyodide skeleton` which creates a package build recipe.
  `pyodide-build mkpkg` will be replaced by `pyodide skeleton pypi`.
  {pr}`3175`

- Added a new CLI command `pyodide build-recipes` which build packages from
  recipe folder. It replaces `pyodide-build buildall`.
  {pr}`3196` {pr}`3279`

- Added a new CLI command `pyodide config` which shows config variables used in
  Pyodide.
  {pr}`3376`

- Added subcommands for `pyodide build` which builds packages from various sources.
  | command | result |
  |------------------------|-----------------------------------------|
  | `pyodide build pypi` | build or fetch a single package from pypi |
  | `pyodide build source` | build the current source folder (same as pyodide build) |
  | `pyodide build url` | build or fetch a package from a url either tgz, tar.gz zip or wheel |
  {pr}`3196`

### Packages

- New packages: pycryptodome {pr}`2965`, coverage-py {pr}`3053`, bcrypt
  {pr}`3125`, lightgbm {pr}`3138`, pyheif, pillow_heif, libheif, libde265
  {pr}`3161`, wordcloud {pr}`3173`, gdal, fiona, geopandas {pr}`3213`, the
  standard library \_hashlib module {pr}`3206` , pyinstrument {pr}`3258`, gensim
  {pr}`3326`, smart_open {pr}`3326`, pyodide-http {pr}`3355`.

- {{ Fix }} Scipy CSR data is now handled correctly in XGBoost.
  {pr}`3194`

- {{ Update }} Upgraded packages: SciPy 1.9.1 {pr}`3043`, pandas 1.5.0
  {pr}`3134`, numpy 1.23.3 {pr}`3284`, scikit-learn 1.1.3 {pr}`3324` as well as
  most of the other packages {pr}`3348` {pr}`3365`. See
  {ref}`packages-in-pyodide` for more details.

- {{ Fix }} Fix scipy handling of exceptions that are raised from C++ code.
  {pr}`3384`.

### List of Contributors

Aierie, dataxerik, David Lechner, Deepak Cherian, Filipe, Gyeongjae Choi, Hood
Chatham, H.Yamada, Jacques Boscq, Jeremy Tuloup, Joe Marshall, John Wason,
Loïc Estève, partev, Patrick Arminio, Péter Ferenc Gyarmati, Prete, Qijia
Liu, Roman Yurchak, ryanking13, skelsec, Starz0r, Will Lachance, YeonWoo, Yizhi
Liu

## Version 0.21.3

_September 15, 2022_

- {{ Fix }} When loading `sqlite3`, `loadPackage` no longer also loads `nltk`
  and `regex`.
  {issue}`3001`

- {{ Fix }} Packages are now loaded in a topologically sorted order regarding
  their dependencies.
  {pr}`3020`

- {{ Breaking }} Loading the `soupsieve` package will not automatically load
  `beautifulsoup4` together.
  {pr}`3020`

- {{ Fix }} Fix the incorrect package name `ruamel` to `ruamel.yaml`.
  {pr}`3036`

- {{ Fix }} `loadPyodide` will now raise error when the version of
  JavaScript and Python Pyodide package does not match.
  {pr}`3074`

- {{ Enhancement }} Pyodide now works with a content security policy that
  doesn't include `unsafe-eval`. It is still necessary to include
  `wasm-unsafe-eval` (and probably always will be). Since current Safari
  versions have no support for `wasm-unsafe-eval`, it is necessary to include
  `unsafe-eval` in order to work in Safari. This will likely be fixed in the
  next Safari release: https://bugs.webkit.org/show_bug.cgi?id=235408
  {pr}`3075`

- {{ Fix }} It works again to use `loadPyodide` with a relative URL as
  `indexURL` (this was a regression in v0.21.2).
  {pr}`3077`

- {{ Fix }} Add `url` to list of pollyfilled packages for webpack compatibility.
  {pr}`3080`

- {{ Fix }} Fixed warnings like
  `Critical dependency: the request of a dependency is an expression.`
  when using Pyodide with webpack.
  {pr}`3080`

- {{ Enhancement }} Add binary files to exports in JavaScript package
  {pr}`3085`.

- {{ Fix }} Source maps are included in the distribution again (reverting
  {pr}`3015` included in 0.21.2) and if there is a variable in top level scope
  called `__dirname` we use that for the `indexURL`.
  {pr}`3088`

- {{ Fix }} `PyProxy.apply` now correctly handles the case when something
  unexpected is passed as the second argument.
  {pr}`3101`

## Version 0.21.2

_August 29, 2022_

- {{ Fix }} The standard library packages `ssl` and `lzma` can now be installed
  with `pyodide.loadPackage("ssl")` or `micropip.install("ssl")` (previously
  they had a leading underscore and it was only possible to load them with
  `pyodide.loadPackage`).
  {issue}`3003`

- {{ Fix }} If a wheel path is passed to `pyodide.loadPackage`, it will now be
  resolved relative to `document.location` (in browser) or relative to the
  current working directory (in Node) rather than relative to `indexURL`.
  {pr}`3013`, {issue}`3011`

- {{ Fix }} Fixed a bug in Emscripten that caused Pyodide to fail in Jest.
  {pr}`3014`

- {{ Fix }} It now works to pass a relative url to `indexURL`. Also, the
  calculated index URL now works even if `node` is run with
  `--enable-source-maps`.
  {pr}`3015`

## Version 0.21.1

_August 22, 2022_

- New packages: the standard library lzma module {pr}`2939`

- {{ Enhancement }} Pyodide now shows more helpful error messages when importing
  unvendored or removed stdlib modules fails.
  {pr}`2973`

- {{ Breaking }} The default value of `fullStdLib` in `loadPyodide` has been
  changed to `false`. This means Pyodide now will not load some stdlib modules
  like distutils, ssl, and sqlite3 by default. See [Pyodide Python
  compatibility](https://pyodide.org/en/stable/usage/wasm-constraints.html) for
  detail. If `fullStdLib` is set to `true`, it will load all unvendored stdlib
  modules. However, setting `fullStdLib` to true will increase the initial
  Pyodide load time. So it is preferable to explicitly load the required module.
  {pr}`2998`

- {{ Enhancement }} `pyodide build` now checks that the correct version of the
  Emscripten compiler is used.
  {pr}`2975`, {pr}`2990`

- {{ Fix }} Pyodide works in Safari v14 again. It was broken in v0.21.0
  {pr}`2994`

## Version 0.21.0

_August 9, 2022_

[See the release notes for a summary.](https://blog.pyodide.org/posts/0.21-release/)

### Build system

- {{ Enhancement }} Emscripten was updated to Version 3.1.14
  {pr}`2775`, {pr}`2679`, {pr}`2672`

- {{ Fix }} Fix building on macOS {issue}`2360` {pr}`2554`

- {{ Enhancement }} Update Typescript target to ES2017 to generate more modern
  Javascript code.
  {pr}`2471`

- {{ Enhancement }} We now put our built files into the `dist` directory rather
  than the `build` directory. {pr}`2387`

- {{ Fix }} The build will error out earlier if `cmake` or `libtool` are not
  installed.
  {pr}`2423`

- {{ Enhancement }} The platform tags of wheels now include the Emscripten
  version in them. This should help ensure ABI compatibility if Emscripten
  wheels are distributed outside of the main Pyodide distribution.
  {pr}`2610`

- {{ Enhancement }} The build system now uses the sysconfigdata from the target
  Python rather than the host Python.
  {pr}`2516`

- {{ Enhancement }} Pyodide now builds with `-sWASM_BIGINT`.
  {pr}`2643`

- {{ Enhancement }} Added `cross-script` key to the `meta.yaml` spec to allow
  executing custom logic in the cross build environment.
  {pr}`2734`

### Pyodide Module and type conversions

- {{ API }} All functions were moved out of the root `pyodide` package into
  various submodules. For backwards compatibility, they will be available from
  the root package (raising a `FutureWarning`) until v0.23.0.
  {pr}`2787`, {pr}`2790`

- {{ Enhancement }} `loadPyodide` no longer uses any global state, so it can be
  used more than once in the same thread. This is recommended if a network
  request causes a loading failure, if there is a fatal error, if you damage the
  state of the runtime so badly that it is no longer usable, or for certain
  testing purposes. It is not recommended for creating multiple execution
  environments, for which you should use
  `pyodide.runPython(code, { globals : some_dict})`;
  {pr}`2391`

- {{ Enhancement }} `pyodide.unpackArchive` now accepts any `ArrayBufferView` or
  `ArrayBuffer` as first argument, rather than only a `Uint8Array`.
  {pr}`2451`

- {{ Feature }} Added `pyodide.code.run_js` API.
  {pr}`2426`

- {{ Fix }} BigInt's between 2^{32\*n - 1} and 2^{32\*n} no longer get
  translated to negative Python ints.
  {pr}`2484`

- {{ Fix }} Pyodide now correctly handles JavaScript objects with `null`
  constructor.
  {pr}`2520`

- {{ Fix }} Fix garbage collection of `once_callable` {pr}`2401`

- {{ Enhancement }} Added the `js_id` attribute to `JsProxy` to allow using
  JavaScript object identity as a dictionary key.
  {pr}`2515`

- {{ Fix }} Fixed a bug with `toJs` when used with recursive structures and the
  `dictConverter` argument.
  {pr}`2533`

- {{ Enhancement }} Added Python wrappers `set_timeout`, `clear_timeout`,
  `set_interval`, `clear_interval`, `add_event_listener` and
  `remove_event_listener` for the corresponding JavaScript functions.
  {pr}`2456`

- {{ Fix }} If a request fails due to CORS, `pyfetch` now raises an `OSError`
  not a `JSException`.
  {pr}`2598`

- {{ Enhancement }} Pyodide now directly exposes the Emscripten `PATH` and
  `ERRNO_CODES` APIs.
  {pr}`2582`

- {{ Fix }} The `bool` operator on a `JsProxy` now behaves more consistently: it
  returns `False` if JavaScript would say that `!!x` is `false`, or if `x` is an
  empty container. Otherwise it returns `True`.
  {pr}`2803`

- {{ Fix }} Fix `loadPyodide` errors for the Windows Node environment.
  {pr}`2888`

- {{ Enhancement }} Implemented slice subscripting, `+=`, and `extend` for
  `JsProxy` of Javascript arrays.
  {pr}`2907`

### REPL

- {{ Enhancement }} Add a spinner while the REPL is loading
  {pr}`2635`

- {{ Enhancement }} Cursor blinking in the REPL can be disabled by setting
  `noblink` in URL search params.
  {pr}`2666`

- {{ Fix }} Fix a REPL error in printing high-dimensional lists.
  {pr}`2517` {pr}`2919`

- {{ Fix }} Fix output bug with using `input()` on online console
  {pr}`2509`

### micropip and package loading

- {{ API }} `packages.json` which contains the dependency graph for packages
  was renamed to `repodata.json` to avoid confusion with `package.json` used
  in JavaScript packages.

- {{ Enhancement }} Added SHA-256 hash of package to entries in `repodata.json`
  {pr}`2455`

- {{ Enhancement }} Integrity of Pyodide packages is now verified before
  loading them. This is for now limited to browser environments.
  {pr}`2513`

- {{ Enhancement }} `micropip` supports loading wheels from the Emscripten file
  system using the `emfs:` protocol now.
  {pr}`2767`

- {{ Enhancement }} It is now possible to use an alternate `repodata.json`
  lockfile by passing the `lockFileURL` option to `loadPyodide`. This is
  particularly intended to be used with `micropip.freeze`.
  {pr}`2645`

- {{ Fix }} micropip now correctly handles package names that include dashes
  {pr}`2414`

- {{ Enhancement }} Allow passing `credentials` to `micropip.install()`
  {pr}`2458`

- {{ Enhancement }} {func}`micropip.install` now accepts a `deps` parameter.
  If set to `False`, micropip will not install dependencies of the package.
  {pr}`2433`

- {{ Fix }} micropip now correctly compares packages with prerelease version
  {pr}`2532`

- {{ Enhancement }} {func}`micropip.install` now accepts a `pre` parameter.
  If set to `True`, micropip will include pre-release and development versions.
  {pr}`2542`

- {{ Enhancement }} `micropip` was refactored to improve readability and ease of
  maintenance.
  {pr}`2561`, {pr}`2563`, {pr}`2564`, {pr}`2565`, {pr}`2568`

- {{ Enhancement }} Various error messages were fine tuned and improved.
  {pr}`2562`, {pr}`2558`

- {{ Enhancement }} `micropip` was adjusted to keep its state in the wheel
  `.dist-info` directories which improves consistenency with the Python standard
  library and other tools used to install packages.
  {pr}`2572`

- {{ Enhancement }} `micropip` can now be used to install Emscripten binary wheels.
  {pr}`2591`

- {{ Enhancement }} Added `micropip.freeze` to record the current set of loaded
  packages into a `repodata.json` file.
  {pr}`2581`

- {{ Fix }} `micropip.list` now works correctly when there are packages
  that are installed via `pyodide.loadPackage` from a custom URL.
  {pr}`2743`

- {{ Fix }} micropip now skips package versions which do not follow PEP440.
  {pr}`2754`

- {{ Fix }} `micropip` supports extra markers in packages correctly now.
  {pr}`2584`

### Packages

- {{ Enhancement }} Update sqlite version to latest stable release
  {pr}`2477` and {pr}`2518`

- {{ Enhancement }} Pillow now supports WEBP image format {pr}`2407`.

- {{ Enhancement }} Pillow and opencv-python now support the TIFF image format.
  {pr}`2762`

- Pandas is now compiled with `-Oz`, which significantly speeds up loading the library
  on Chrome {pr}`2457`

- New packages: opencv-python {pr}`2305`, ffmpeg {pr}`2305`, libwebp {pr}`2305`,
  h5py, pkgconfig and libhdf5 {pr}`2411`, bitarray {pr}`2459`, gsw {pr}`2511`,
  cftime {pr}`2504`, svgwrite, jsonschema, tskit {pr}`2506`, xarray {pr}`2538`,
  demes, libgsl, newick, ruamel, msprime {pr}`2548`, gmpy2 {pr}`2665`,
  xgboost {pr}`2537`, galpy {pr}`2676`, shapely, geos {pr}`2725`, suitesparse,
  sparseqr {pr}`2685`, libtiff {pr}`2762`, pytest-benchmark {pr}`2799`,
  termcolor {pr}`2809`, sqlite3, libproj, pyproj, certifi {pr}`2555`,
  rebound {pr}`2868`, reboundx {pr}`2909`, pyclipper {pr}`2886`,
  brotli {pr}`2925`, python-magic {pr}`2941`

### Miscellaneous

- {{ Fix }} We now tell packagers (e.g., Webpack) to ignore npm-specific imports
  when packing files for the browser.
  {pr}`2468`

- {{ Enhancement }} `run_in_pyodide` now has support for pytest assertion
  rewriting and decorators such as `pytest.mark.parametrize` and hypothesis.
  {pr}`2510`, {pr}`2541`

- {{ Breaking }} `pyodide_build.testing` is removed. `run_in_pyodide`
  decorator can now be accessed through
  [`pytest-pyodide`](https://github.com/pyodide/pytest-pyodide) package.
  {pr}`2418`

### List of contributors

Alexey Ignatiev, Andrey Smelter, andrzej, Antonio Cuni, Ben Jeffery, Brian
Benjamin Maranville, David Lechner, dragoncoder047, echorand (Amit Saha),
Filipe, Frank, Gyeongjae Choi, Hanno Rein, haoran1062, Henry Schreiner, Hood
Chatham, Jason Grout, jmdyck, Jo Bovy, John Wason, josephrocca, Kyle Cutler,
Lester Fan, Liumeo, lukemarsden, Mario Gersbach, Matt Toad, Michael Droettboom,
Michael Gilbert, Michael Neil, Mu-Tsun Tsai, Nicholas Bollweg, pysathq, Ricardo
Prins, Rob Gries, Roman Yurchak, Ryan May, Ryan Russell, stonebig, Szymswiat,
Tobias Megies, Vic Kumar, Victor, Wei Ji, Will Lachance

## Version 0.20.0

_April 9th, 2022_

[See the release notes for a summary.](https://blog.pyodide.org/posts/0.20-release/)

### CPython and stdlib

- {{ Update }} Pyodide now runs Python 3.10.2.
  {pr}`2225`

- {{ Enhancement }} All `ctypes` tests pass now except for
  `test_callback_too_many_args` (and we have a plan to fix
  `test_callback_too_many_args` upstream). `libffi-emscripten` now also passes
  all libffi tests.
  {pr}`2350`

### Packages

- {{Fix}} matplotlib now loads multiple fonts correctly {pr}`2271`

- New packages: boost-histogram {pr}`2174`, cryptography v3.3.2 {pr}`2263`, the
  standard library ssl module {pr}`2263`, python-solvespace v3.0.7,
  lazy-object-proxy {pr}`2320`.

- Many more scipy linking errors were fixed, mostly related to the Fortran f2c
  ABI for string arguments. There are still some fatal errors in the Scipy test
  suite, but none seem to be simple linker errors.
  {pr}`2289`

- Removed pyodide-interrupts. If you were using this for some reason, use
  `pyodide.setInterruptBuffer` instead.
  {pr}`2309`

- Most included packages were updated to the latest version. See
  {ref}`packages-in-pyodide` for a full list.

### Type translations

- {{Fix}} Python tracebacks now include Javascript frames when Python calls a
  Javascript function.
  {pr}`2123`

- {{Enhancement}} Added a `default_converter` argument to `JsProxy.to_py`
  and `pyodide.toPy` which is used to process any object that doesn't have
  a built-in conversion to Python. Also added a `default_converter` argument to
  `PyProxy.toJs` and `pyodide.ffi.to_js` to convert.
  {pr}`2170` and {pr}`2208`

- {{ Enhancement }} Async Python functions called from Javascript now have the
  resulting coroutine automatically scheduled. For instance, this makes it
  possible to use an async Python function as a Javascript event handler.
  {pr}`2319`

### Javascript package

- {{Enhancement}} It is no longer necessary to provide `indexURL` to
  `loadPyodide`.
  {pr}`2292`

- {{ Breaking }} The `globals` argument to `pyodide.runPython` and
  `pyodide.runPythonAsync` is now passed as a named argument. The old usage
  still works with a deprecation warning.
  {pr}`2300`

- {{Enhancement}} The Javascript package was migrated to Typescript.
  {pr}`2130` and {pr}`2133`

- {{Fix}} Fix importing pyodide with ESM syntax in a module type web worker.
  {pr}`2220`

- {{Enhancement}} When Pyodide is loaded as an ES6 module, no global
  `loadPyodide` variable is created (instead, it should be accessed as an
  attribute on the module).
  {pr}`2249`

- {{Fix}} The type `Py2JsResult` has been replaced with `any` which is more
  accurate. For backwards compatibility, we still export `Py2JsResult` as an
  alias for `any`.
  {pr}`2277`

- {{Fix}} Pyodide now loads correctly even if requirejs is included.
  {pr}`2283`

- {{ Enhancement }} Added robust handling for non-`Error` objects thrown by
  Javascript code. This mostly should never happen since well behaved Javascript
  code ought to throw errors. But it's better not to completely crash if it
  throws something else.
  {pr}`2294`

### pyodide_build

- {{Enhancement}} Pyodide now uses Python wheel files to distribute packages
  rather than the emscripten `file_packager.py` format.
  {pr}`2027`

- {{Enhancement}} Pyodide now uses `pypa/build` to build packages. We (mostly)
  use build isolation, so we can build packages that require conflicting
  versions of setuptools or alternative build backends.
  {pr}`2272`

- {{Enhancement}} Most pure Python packages were switched to use the wheels
  directly from PyPI rather than rebuilding them.
  {pr}`2126`

- {{Enhancement}} Added support for C++ exceptions in packages. Now C++
  extensions compiled and linked with `-fexceptions` can catch C++ exceptions.
  Furthermore, uncaught C++ exceptions will be formatted in a human-readable
  way.
  {pr}`2178`

- {{Breaking}} Removed the `skip-host` key from the `meta.yaml` format. If
  needed, install a host copy of the package with pip instead.
  {pr}`2256`

### Uncategorized

- {{ Enhancement }} The interrupt buffer can be used to raise all 64 signals
  now, not just `SIGINT`. Write a number between `1<= signum <= 64` into the
  interrupt buffer to trigger the corresponding signal. By default everything
  but `SIGINT` will be ignored. Any value written into the interrupt buffer
  outside of the range from 1 to 64 will be silently discarded.
  {pr}`2301`

- {{ Enhancement }} Updated to Emscripten 2.0.27.
  {pr}`2295`

- {{ Breaking }} The `extractDir` argument to `pyodide.unpackArchive` is now
  passed as a named argument. The old usage still works with a deprecation
  warning.
  {pr}`2300`

- {{ Enhancement }} Support ANSI escape codes in the Pyodide console.
  {pr}`2345`

- {{ Fix }} `pyodide_build` can now be installed in non-editable ways.
  {pr}`2351`

### List of contributors

Boris Feld, Christian Staudt, Gabriel Fougeron, Gyeongjae Choi, Henry Schreiner,
Hood Chatham, Jo Bovy, Karthikeyan Singaravelan, Leo Psidom, Liumeo, Luka
Mamukashvili, Madhur Tandon, Paul Korzhyk, Roman Yurchak, Seungmin Kim, Thorsten
Beier, Tom White, and Will Lachance

## Version 0.19.1

_February 19, 2022_

### Packages

- New packages: sqlalchemy {pr}`2112`, pydantic {pr}`2117`, wrapt {pr}`2165`

- {{ Update }} Upgraded packages: pyb2d (0.7.2), {pr}`2117`

- {{Fix}} A fatal error in `scipy.stats.binom.ppf` has been fixed.
  {pr}`2109`

- {{Fix}} Type signature mismatches in some numpy comparators have been fixed.
  {pr}`2110`

### Type translations

- {{Fix}} The "PyProxy has already been destroyed" error message has been
  improved with some context information.
  {pr}`2121`

### REPL

- {{Enhancement}} Pressing TAB in REPL no longer triggers completion when input
  is whitespace. {pr}`2125`

### List of contributors

Christian Staudt, Gyeongjae Choi, Hood Chatham, Liumeo, Paul Korzhyk, Roman
Yurchak, Seungmin Kim, Thorsten Beier

## Version 0.19.0

_January 10, 2021_

[See the release notes for a summary.](https://blog.pyodide.org/posts/0.19-release/)

### Python package

- {{Enhancement}} If `find_imports` is used on code that contains a syntax
  error, it will return an empty list instead of raising a `SyntaxError`.
  {pr}`1819`

- {{Enhancement}} Added the `pyodide.http.pyfetch` API which provides a
  convenience wrapper for the Javascript `fetch` API. The API returns a response
  object with various methods that convert the data into various types while
  minimizing the number of times the data is copied.
  {pr}`1865`

- {{Enhancement}} Added the `unpack_archive` API to the `pyodide.http.FetchResponse`
  object which treats the response body as an archive and uses `shutil` to
  unpack it. {pr}`1935`

- {{Fix}} The Pyodide event loop now works correctly with cancelled handles. In
  particular, `asyncio.wait_for` now functions as expected.
  {pr}`2022`

### JavaScript package

- {{Fix}} `loadPyodide` no longer fails in the
  presence of a user-defined global named `process`.
  {pr}`1849`

- {{Fix}} Various webpack buildtime and runtime compatibility issues were fixed.
  {pr}`1900`

- {{Enhancement}} Added the `pyodide.pyimport` API to import a Python module and
  return it as a `PyProxy`. Warning: this is different from the original
  `pyimport` API which was removed in this version.
  {pr}`1944`

- {{Enhancement}} Added the `pyodide.unpackArchive` API which unpacks an archive
  represented as an ArrayBuffer into the working directory. This is intended as
  a way to install packages from a local application.
  {pr}`1944`

- {{API}} `loadPyodide` now accepts a `homedir` parameter which sets home
  directory of Pyodide virtual file system.
  {pr}`1936`

- {{Breaking}} The default working directory(home directory) inside the Pyodide
  virtual file system has been changed from `/` to `/home/pyodide`. To get the
  previous behavior, you can
  - call `os.chdir("/")` in Python to change working directory or
  - call `loadPyodide` with the `homedir="/"`
    argument
    {pr}`1936`

### Python / JavaScript type conversions

- {{Breaking}} Updated the calling convention when a JavaScript function is
  called from Python to improve memory management of PyProxies. PyProxy
  arguments and return values are automatically destroyed when the function is
  finished.
  {pr}`1573`

- {{Enhancement}} Added `JsProxy.to_string`, `JsProxy.to_bytes`, and
  `JsProxy.to_memoryview` to allow for conversion of `TypedArray` to standard
  Python types without unneeded copies.
  {pr}`1864`

- {{Enhancement}} Added `JsProxy.to_file` and `JsProxy.from_file` to allow
  reading and writing Javascript buffers to files as a byte stream without
  unneeded copies.
  {pr}`1864`

- {{Fix}} It is now possible to destroy a borrowed attribute `PyProxy` of a
  `PyProxy` (as introduced by {pr}`1636`) before destroying the root `PyProxy`.
  {pr}`1854`

- {{Fix}} If `__iter__()` raises an error, it is now handled correctly by the
  `PyProxy[Symbol.iterator()]` method.
  {pr}`1871`

- {{Fix}} Borrowed attribute `PyProxy`s are no longer destroyed when the root
  `PyProxy` is garbage collected (because it was leaked). Doing so has no
  benefit to nonleaky code and turns some leaky code into broken code (see
  {issue}`1855` for an example).
  {pr}`1870`

- {{Fix}} Improved the way that `pyodide.globals.get("builtin_name")` works.
  Before we used `__main__.__dict__.update(builtins.__dict__)` which led to
  several undesirable effects such as `__name__` being equal to `"builtins"`.
  Now we use a proxy wrapper to replace `pyodide.globals.get` with a function
  that looks up the name on `builtins` if lookup on `globals` fails.
  {pr}`1905`

- {{Enhancement}} Coroutines have their memory managed in a more convenient way.
  In particular, now it is only necessary to either `await` the coroutine or
  call one of `.then`, `.except` or `.finally` to prevent a leak. It is no
  longer necessary to manually destroy the coroutine. Example: before:

```js
async function runPythonAsync(code, globals) {
  let coroutine = Module.pyodide_py.eval_code_async(code, globals);
  try {
    return await coroutine;
  } finally {
    coroutine.destroy();
  }
}
```

After:

```js
async function runPythonAsync(code, globals) {
  return await Module.pyodide_py.eval_code_async(code, globals);
}
```

{pr}`2030`

### pyodide-build

- {{API}} By default only a minimal set of packages is built. To build all
  packages set `PYODIDE_PACKAGES='*'` In addition, `make minimal` was removed,
  since it is now equivalent to `make` without extra arguments.
  {pr}`1801`

- {{Enhancement}} It is now possible to use `pyodide-build buildall` and
  `pyodide-build buildpkg` directly.
  {pr}`2063`

- {{Enhancement}} Added a `--force-rebuild` flag to `buildall` and `buildpkg`
  which rebuilds the package even if it looks like it doesn't need to be
  rebuilt. Added a `--continue` flag which keeps the same source tree for the
  package and can continue from the middle of a build.
  {pr}`2069`

- {{Enhancement}} Changes to environment variables in the build script are now
  seen in the compile and post build scripts.
  {pr}`1706`

- {{Fix}} Fix usability issues with `pyodide-build mkpkg` CLI.
  {pr}`1828`

- {{ Enhancement }} Better support for ccache when building Pyodide
  {pr}`1805`

- {{Fix}} Fix compile error `wasm-ld: error: unknown argument: --sort-common`
  and `wasm-ld: error: unknown argument: --as-needed` in ArchLinux.
  {pr}`1965`

### micropip

- {{Fix}} micropip now raises an error when installing a non-pure python wheel
  directly from a url.
  {pr}`1859`

- {{Enhancement}} {func}`micropip.install` now accepts a `keep_going` parameter.
  If set to `True`, micropip reports all identifiable dependencies that don't
  have pure Python wheels, instead of failing after processing the first one.
  {pr}`1976`

- {{Enhancement}} Added a new API {func}`micropip.list` which returns the list
  of installed packages by micropip.
  {pr}`2012`

### Packages

- {{ Enhancement }} Unit tests are now unvendored from Python packages and
  included in a separate package `<package name>-tests`. This results in a
  20% size reduction on average for packages that vendor tests (e.g. numpy,
  pandas, scipy).
  {pr}`1832`

- {{ Update }} Upgraded SciPy to 1.7.3. There are known issues with some SciPy
  components, the current status of the scipy test suite is
  [here](https://github.com/pyodide/pyodide/pull/2065#issuecomment-1004243045)
  {pr}`2065`

- {{ Fix }} The built-in pwd module of Python, which provides a Unix specific
  feature, is now unvendored.
  {pr}`1883`

- {{Fix}} pillow and imageio now correctly encode/decode grayscale and
  black-and-white JPEG images.
  {pr}`2028`

- {{Fix}} The numpy fft module now works correctly.
  {pr}`2028`

- New packages: logbook {pr}`1920`, pyb2d {pr}`1968`, and threadpoolctl (a
  dependency of scikit-learn) {pr}`2065`

- Upgraded packages: numpy (1.21.4) {pr}`1934`, scikit-learn (1.0.2) {pr}`2065`,
  scikit-image (0.19.1) {pr}`2005`, msgpack (1.0.3) {pr}`2071`, astropy (5.0.3)
  {pr}`2086`, statsmodels (0.13.1) {pr}`2073`, pillow (9.0.0) {pr}`2085`. This
  list is not exhaustive, refer to `packages.json` for the full list.

### Uncategorized

- {{ Enhancement }} `PyErr_CheckSignals` now works with the keyboard interrupt
  system so that cooperative C extensions can be interrupted. Also, added the
  `pyodide.checkInterrupt` function so Javascript code can opt to be
  interrupted.
  {pr}`1294`

- {{Fix}} The `_` variable is now set by the Pyodide repl just like it is set in
  the native Python repl.
  {pr}`1904`

- {{ Enhancement }} `pyodide-env` and `pyodide` Docker images are now available from both
  the [Docker Hub](https://hub.docker.com/repository/docker/pyodide/pyodide-env) and
  from the [Github Package registry](https://github.com/orgs/pyodide/packages). {pr}`1995`

- {{Fix}} The console now correctly handles it when an object's `__repr__` function raises an exception.
  {pr}`2021`

- {{ Enhancement }} Removed the `-s EMULATE_FUNCTION_POINTER_CASTS` flag,
  yielding large benefits in speed, stack usage, and code size.
  {pr}`2019`

### List of contributors

Alexey Ignatiev, Alex Hall, Bart Broere, Cyrille Bogaert, etienne, Grimmer,
Grimmer Kang, Gyeongjae Choi, Hao Zhang, Hood Chatham, Ian Clester, Jan Max
Meyer, LeoPsidom, Liumeo, Michael Christensen, Owen Ou, Roman Yurchak, Seungmin
Kim, Sylvain, Thorsten Beier, Wei Ouyang, Will Lachance

## Version 0.18.1

_September 16, 2021_

### Console

- {{Fix}} Ctrl+C handling in console now works correctly with multiline input.
  New behavior more closely approximates the behavior of the native Python
  console.
  {pr}`1790`

- {{Fix}} Fix the repr of Python objects (including lists and dicts) in console {pr}`1780`

- {{Fix}} The "long output truncated" message now appears on a separate line as intended.
  {pr}`1814`

- {{Fix}} The streams that are used to redirect stdin and stdout in the console now define
  `isatty` to return `True`. This fixes pytest.
  {pr}`1822`

### Python package

- {{Fix}} Avoid circular references when runsource raises SyntaxError
  {pr}`1758`

### JavaScript package

- {{Fix}} The `pyodide.setInterruptBuffer` command is now publicly exposed
  again, as it was in v0.17.0. {pr}`1797`

### Python / JavaScript type conversions

- {{Fix}} Conversion of very large strings from JavaScript to Python works
  again. {pr}`1806`

- {{Fix}} Fixed a use after free bug in the error handling code.
  {pr}`1816`

### Packages

- {{Fix}} pillow now correctly encodes/decodes RGB JPEG image format. {pr}`1818`

### Micellaneous

- {{Fix}} Patched emscripten to make the system calls to duplicate file
  descriptors closer to posix-compliant. In particular, this fixes the use of
  `dup` on pipes and temporary files, as needed by `pytest`.
  {pr}`1823`

## Version 0.18.0

_August 3rd, 2021_

### General

- {{ Update }} Pyodide now runs Python 3.9.5.
  {pr}`1637`

- {{ Enhancement }} Pyodide can experimentally be used in Node.js {pr}`1689`

- {{ Enhancement }} Pyodide now directly exposes the [Emscripten filesystem
  API](https://emscripten.org/docs/api_reference/Filesystem-API.html), allowing
  for direct manipulation of the in-memory filesystem
  {pr}`1692`

- {{ Enhancement }} Pyodide's support of [emscripten file
  systems](https://emscripten.org/docs/api_reference/Filesystem-API.html#file-systems)
  is expanded from the default `MEMFS` to include `IDBFS`, `NODEFS`, `PROXYFS`,
  and `WORKERFS`, allowing for custom persistence strategies depending on
  execution environment {pr}`1596`

- {{ API }} The `packages.json` schema for Pyodide was redesigned for better
  compatibility with conda. {pr}`1700`

- {{ API }} `run_docker` no longer binds any port to the docker image by default.
  {pr}`1750`

### Standard library

- {{ API }} The following standard library modules are now available as standalone packages

  - distlib

  They are loaded by default in `loadPyodide`, however this behavior
  can be disabled with the `fullStdLib` parameter set to `false`.
  All optional stdlib modules can then be loaded as needed with
  `pyodide.loadPackage`. {pr}`1543`

- {{ Enhancement }} The standard library module `audioop` is now included, making the `wave`,
  `sndhdr`, `aifc`, and `sunau` modules usable. {pr}`1623`

- {{ Enhancement }} Added support for `ctypes`.
  {pr}`1656`

### JavaScript package

- {{ Enhancement }} The Pyodide JavaScript package is released to npm under [npmjs.com/package/pyodide](https://www.npmjs.com/package/pyodide)
  {pr}`1762`
- {{ API }} `loadPyodide` no longer automatically
  stores the API into a global variable called `pyodide`. To get old behavior,
  say `globalThis.pyodide = await loadPyodide({...})`.
  {pr}`1597`
- {{ Enhancement }} `loadPyodide` now accepts callback functions for
  `stdin`, `stdout` and `stderr`
  {pr}`1728`
- {{ Enhancement }} Pyodide now ships with first party typescript types for the entire
  JavaScript API (though no typings are available for `PyProxy` fields).
  {pr}`1601`

- {{ Enhancement }} It is now possible to import `Comlink` objects into Pyodide after
  using `pyodide.registerComlink`
  {pr}`1642`

- {{ Enhancement }} If a Python error occurs in a reentrant `runPython` call, the error
  will be propagated into the outer `runPython` context as the original error
  type. This is particularly important if the error is a `KeyboardInterrupt`.
  {pr}`1447`

### Python package

- {{ Enhancement }} Added a new `pyodide.code.CodeRunner` API for finer control than
  `eval_code` and `eval_code_async`. Designed with
  the needs of REPL implementations in mind.
  {pr}`1563`

- {{ Enhancement }} Added `pyodide.console.Console` class closely based on the Python standard
  library `code.InteractiveConsole` but with support for top level await and
  stream redirection. Also added the subclass `pyodide.console.PyodideConsole` which
  automatically uses `pyodide.loadPackagesFromImports` on the code before running
  it.
  {pr}`1125`, {pr}`1155`, {pr}`1635`

- {{ Fix }} `pyodide.code.eval_code_async` no longer automatically awaits a returned
  coroutine or attempts to await a returned generator object (which triggered an
  error).
  {pr}`1563`

### Python / JavaScript type conversions

- {{ API }} `pyodide.runPythonAsync` no longer automatically calls
  `pyodide.loadPackagesFromImports`.
  {pr}`1538`.
- {{ Enhancement }} Added the `PyProxy.callKwargs` method to allow using
  Python functions with keyword arguments from JavaScript.
  {pr}`1539`
- {{ Enhancement }} Added the `PyProxy.copy` method.
  {pr}`1549` {pr}`1630`
- {{ API }} Updated the method resolution order on `PyProxy`. Performing a
  lookup on a `PyProxy` will prefer to pick a method from the `PyProxy` api, if
  no such method is found, it will use `getattr` on the proxied object.
  Prefixing a name with `$` forces `getattr`. For instance, `PyProxy.destroy`
  now always refers to the method that destroys the proxy, whereas
  `PyProxy.$destroy` refers to an attribute or method called `destroy` on the
  proxied object.
  {pr}`1604`
- {{ API }} It is now possible to use `Symbol` keys with PyProxies. These
  `Symbol` keys put markers on the PyProxy that can be used by external code.
  They will not currently be copied by `PyProxy.copy`.
  {pr}`1696`
- {{ Enhancement }} Memory management of `PyProxy` fields has been changed so
  that fields looked up on a `PyProxy` are "borrowed" and have their lifetime
  attached to the base `PyProxy`. This is intended to allow for more idiomatic
  usage.
  (See {issue}`1617`.) {pr}`1636`
- {{ API }} The depth argument to `toJs` is now passed as an option, so
  `toJs(n)` in v0.17 changed to `toJs({depth : n})`. Similarly, `pyodide.toPy`
  now takes `depth` as a named argument. Also `to_js` and `to_py` only take
  depth as a keyword argument.
  {pr}`1721`
- {{ API }} `PyProxy.toJs` and `pyodide.ffi.to_js` now
  take an option `pyproxies`, if a JavaScript Array is passed for this, then
  any proxies created during conversion will be placed into this array. This
  allows easy cleanup later. The `create_pyproxies` option can be used to
  disable creation of pyproxies during conversion (instead a `ConversionError`
  is raised). {pr}`1726`
- {{ API }} `toJs` and `to_js` now take an option `dict_converter` which will be
  called on a JavaScript iterable of two-element Arrays as the final step of
  converting dictionaries. For instance, pass `Object.fromEntries` to convert to
  an object or `Array.from` to convert to an array of pairs.
  {pr}`1742`

### pyodide-build

- {{ API }} pyodide-build is now an installable Python package, with an
  identically named CLI entrypoint that replaces `bin/pyodide` which is removed
  {pr}`1566`

### micropip

- {{ Fix }} micropip now correctly handles packages that have mixed case names.
  (See {issue}`1614`).
  {pr}`1615`
- {{ Enhancement }} micropip now resolves dependencies correctly for old
  versions of packages (it used to always use the dependencies from the most
  recent version, see {issue}`1619` and {issue}`1745`). micropip also will
  resolve dependencies for wheels loaded from custom urls.
  {pr}`1753`

### Packages

- {{ Enhancement }} matplotlib now comes with a new renderer based on the html5 canvas element. {pr}`1579`
  It is optional and the current default backend is still the agg backend compiled to wasm.
- {{ Enhancement }} Updated a number of packages included in Pyodide.

### List of contributors

Albertas Gimbutas, Andreas Klostermann, Arfy Slowy, daoxian,
Devin Neal, fuyutarow, Grimmer, Guido Zuidhof, Gyeongjae Choi, Hood
Chatham, Ian Clester, Itay Dafna, Jeremy Tuloup, jmsmdy, LinasNas, Madhur
Tandon, Michael Christensen, Nicholas Bollweg, Ondřej Staněk, Paul m. p. P,
Piet Brömmel, Roman Yurchak, stefnotch, Syrus Akbary, Teon L Brooks, Waldir

## Version 0.17.0

_April 21, 2021_

See the {ref}`0-17-0-release-notes` for more information.

### Improvements to package loading and dynamic linking

- {{ Enhancement }} Uses the emscripten preload plugin system to preload .so files in packages
- {{ Enhancement }} Support for shared library packages. This is used for CLAPACK which makes scipy a lot smaller.
  {pr}`1236`
- {{ Fix }} Pyodide and included packages can now be used with Safari v14+.
  Safari v13 has also been observed to work on some (but not all) devices.

### Python / JS type conversions

- {{ Feature }} A `JsProxy` of a JavaScript `Promise` or other awaitable object is now a
  Python awaitable.
  {pr}`880`
- {{ API }} Instead of automatically converting Python lists and dicts into
  JavaScript, they are now wrapped in `PyProxy`. Added a new `PyProxy.toJs`
  API to request the conversion behavior that used to be implicit.
  {pr}`1167`
- {{ API }} Added `JsProxy.to_py` API to convert a JavaScript object to Python.
  {pr}`1244`
- {{ Feature }} Flexible jsimports: it now possible to add custom Python
  "packages" backed by JavaScript code, like the `js` package. The `js` package
  is now implemented using this system.
  {pr}`1146`
- {{ Feature }} A `PyProxy` of a Python coroutine or awaitable is now an
  awaitable JavaScript object. Awaiting a coroutine will schedule it to run on
  the Python event loop using `asyncio.ensure_future`.
  {pr}`1170`
- {{ Enhancement }} Made `PyProxy` of an iterable Python object an iterable Js
  object: defined the `[Symbol.iterator]` method, can be used like `for(let x of proxy)`.
  Made a `PyProxy` of a Python iterator an iterator: `proxy.next()` is
  translated to `next(it)`. Made a `PyProxy` of a Python generator into a
  JavaScript generator: `proxy.next(val)` is translated to `gen.send(val)`.
  {pr}`1180`
- {{ API }} Updated `PyProxy` so that if the wrapped Python object supports `__getitem__`
  access, then the wrapper has `get`, `set`, `has`, and `delete` methods which do
  `obj[key]`, `obj[key] = val`, `key in obj` and `del obj[key]` respectively.
  {pr}`1175`
- {{ API }} The `pyodide.pyimport` function is deprecated in favor of using
  `pyodide.globals.get('key')`. {pr}`1367`
- {{ API }} Added `PyProxy.getBuffer` API to allow direct access to Python
  buffers as JavaScript TypedArrays.
  {pr}`1215`
- {{ API }} The innermost level of a buffer converted to JavaScript used to be a
  TypedArray if the buffer was contiguous and otherwise an Array. Now the
  innermost level will be a TypedArray unless the buffer format code is a '?' in
  which case it will be an Array of booleans, or if the format code is a "s" in
  which case the innermost level will be converted to a string.
  {pr}`1376`
- {{ Enhancement }} JavaScript `BigInt`s are converted into Python `int` and
  Python `int`s larger than 2^53 are converted into `BigInt`.
  {pr}`1407`
- {{ API }} Added `pyodide.isPyProxy` to test if an object is a `PyProxy`.
  {pr}`1456`
- {{ Enhancement }} `PyProxy` and `PyBuffer` objects are now garbage collected
  if the browser supports `FinalizationRegistry`.
  {pr}`1306`
- {{ Enhancement }} Automatic conversion of JavaScript functions to CPython
  calling conventions.
  {pr}`1051`, {pr}`1080`
- {{ Enhancement }} Automatic detection of fatal errors. In this case Pyodide
  will produce both a JavaScript and a Python stack trace with explicit
  instruction to open a bug report.
  pr`{1151}`, pr`{1390}`, pr`{1478}`.
- {{ Enhancement }} Systematic memory leak detection in the test suite and a
  large number of fixed to memory leaks.
  pr`{1340}`
- {{ Fix }} getattr and dir on JsProxy now report consistent results and include all
  names defined on the Python dictionary backing JsProxy.
  {pr}`1017`
- {{ Fix }} `JsProxy.__bool__` now produces more consistent results: both
  `bool(window)` and `bool(zero-arg-callback)` were `False` but now are `True`.
  Conversely, `bool(empty_js_set)` and `bool(empty_js_map)` were `True` but now
  are `False`.
  {pr}`1061`
- {{ Fix }} When calling a JavaScript function from Python without keyword
  arguments, Pyodide no longer passes a `PyProxy`-wrapped `NULL` pointer as the
  last argument. {pr}`1033`
- {{ Fix }} JsBoundMethod is now a subclass of JsProxy, which fixes nested
  attribute access and various other strange bugs.
  {pr}`1124`
- {{ Fix }} JavaScript functions imported like `from js import fetch` no longer
  trigger "invalid invocation" errors (issue {issue}`461`) and
  `js.fetch("some_url")` also works now (issue {issue}`768`).
  {pr}`1126`
- {{ Fix }} JavaScript bound method calls now work correctly with keyword arguments.
  {pr}`1138`
- {{ Fix }} JavaScript constructor calls now work correctly with keyword
  arguments.
  {pr}`1433`

### pyodide-py package

- {{ Feature }} Added a Python event loop to support asyncio by scheduling
  coroutines to run as jobs on the browser event loop. This event loop is
  available by default and automatically enabled by any relevant asyncio API,
  so for instance `asyncio.ensure_future` works without any configuration.
  {pr}`1158`
- {{ API }} Removed `as_nested_list` API in favor of `JsProxy.to_py`.
  {pr}`1345`

### pyodide-js

- {{ API }} Removed iodide-specific code in `pyodide.js`. This breaks compatibility with
  iodide.
  {pr}`878`, {pr}`981`
- {{ API }} Removed the `pyodide.autocomplete` API, use Jedi directly instead.
  {pr}`1066`
- {{ API }} Removed `pyodide.repr` API.
  {pr}`1067`
- {{ Fix }} If `messageCallback` and `errorCallback` are supplied to
  `pyodide.loadPackage`, `pyodide.runPythonAsync` and
  `pyodide.loadPackagesFromImport`, then the messages are no longer
  automatically logged to the console.
- {{ Feature }} `runPythonAsync` now runs the code with `eval_code_async`. In
  particular, it is possible to use top-level await inside of `runPythonAsync`.
- `eval_code` now accepts separate `globals` and `locals` parameters.
  {pr}`1083`
- Added the `pyodide.setInterruptBuffer` API. This can be used to set a
  `SharedArrayBuffer` to be the keyboard interrupt buffer. If Pyodide is running
  on a webworker, the main thread can signal to the webworker that it should
  raise a `KeyboardInterrupt` by writing to the interrupt buffer.
  {pr}`1148` and {pr}`1173`
- Changed the loading method: added an async function `loadPyodide` to load
  Pyodide to use instead of `languagePluginURL` and `languagePluginLoader`. The
  change is currently backwards compatible, but the old approach is deprecated.
  {pr}`1363`
- `runPythonAsync` now accepts `globals` parameter.
  {pr}`1914`

### micropip

- {{ Feature }} `micropip` now supports installing wheels from relative URLs.
  {pr}`872`
- {{ API }} `micropip.install` now returns a Python `Future` instead of a JavaScript `Promise`.
  {pr}`1324`
- {{ Fix }} `micropip.install` now interacts correctly with
  {js:func}`pyodide.loadPackage`.
  {pr}`1457`
- {{ Fix }} `micropip.install` now handles version constraints correctly
  even if there is a version of the package available from the Pyodide `indexURL`.

### Build system

- {{ Enhancement }} Updated to latest emscripten 2.0.13 with the upstream LLVM backend
  {pr}`1102`
- {{ API }} Use upstream `file_packager.py`, and stop checking package abi versions.
  The `PYODIDE_PACKAGE_ABI` environment variable is no longer used, but is
  still set as some packages use it to detect whether it is being built for
  Pyodide. This usage is deprecated, and a new environment variable `PYODIDE`
  is introduced for this purpose.

  As part of the change, Module.checkABI is no longer present.
  {pr}`991`

- uglifyjs and lessc no longer need to be installed in the system during build
  {pr}`878`.
- {{ Enhancement }} Reduce the size of the core Pyodide package
  {pr}`987`.
- {{ Enhancement }} Optionally to disable docker port binding
  {pr}`1423`.
- {{ Enhancement }} Run arbitrary command in docker
  {pr}`1424`
- Docker images for Pyodide are now accessible at
  [pyodide/pyodide-env](https://hub.docker.com/repository/docker/pyodide/pyodide-env)
  and
  [pyodide/pyodide](https://hub.docker.com/repository/docker/pyodide/pyodide).
- {{ Enhancement }} Option to run docker in non-interactive mode
  {pr}`1641`

### REPL

- {{ Fix }} In console.html: sync behavior, full stdout/stderr support, clean namespace,
  bigger font, correct result representation, clean traceback
  {pr}`1125` and {pr}`1141`
- {{ Fix }} Switched from ̀Jedi to rlcompleter for completion in
  `pyodide.console.InteractiveConsole` and so in `console.html`. This fixes
  some completion issues (see {issue}`821` and {issue}`1160`)
- {{ Enhancement }} Support top-level await in the console
  {pr}`1459`

### Packages

- six, jedi and parso are no longer vendored in the main Pyodide package, and
  need to be loaded explicitly
  {pr}`1010`, {pr}`987`.
- Updated packages {pr}`1021`, {pr}`1338`, {pr}`1460`.
- Added Plotly version 4.14.3 and retrying dependency
  {pr}`1419`

### List of contributors

(in alphabetic order)

Aditya Shankar, casatir, Dexter Chua, dmondev, Frederik Braun, Hood Chatham,
Jan Max Meyer, Jeremy Tuloup, joemarshall, leafjolt, Michael Greminger,
Mireille Raad, Ondřej Staněk, Paul m. p. P, rdb, Roman Yurchak, Rudolfs

## Version 0.16.1

_December 25, 2020_

Note: due to a CI deployment issue the 0.16.0 release was skipped and replaced
by 0.16.1 with identical contents.

- Pyodide files are distributed by [JsDelivr](https://www.jsdelivr.com/),
  `https://cdn.jsdelivr.net/pyodide/v0.16.1/full/pyodide.js`
  The previous CDN `pyodide-cdn2.iodide.io` still works and there
  are no plans for deprecating it. However please use
  JsDelivr as a more sustainable solution, including for earlier Pyodide
  versions.

### Python and the standard library

- Pyodide includes CPython 3.8.2
  {pr}`712`
- ENH Patches for the threading module were removed in all packages. Importing
  the module, and a subset of functionality (e.g. locks) works, while starting
  a new thread will produce an exception, as expected.
  {pr}`796`.
  See {issue}`237` for the current status of the threading support.
- ENH The multiprocessing module is now included, and will not fail at import,
  thus avoiding the necessity to patch included packages. Starting a new
  process will produce an exception due to the limitation of the WebAssembly VM
  with the following message: `Resource temporarily unavailable`
  {pr}`796`.

### Python / JS type conversions

- FIX Only call `Py_INCREF()` once when proxied by PyProxy
  {pr}`708`
- JavaScript exceptions can now be raised and caught in Python. They are
  wrapped in pyodide.JsException.
  {pr}`891`

### pyodide-py package and micropip

- The `pyodide.py` file was transformed to a pyodide-py package. The imports
  remain the same so this change is transparent to the users
  {pr}`909`.
- FIX Get last version from PyPI when installing a module via micropip
  {pr}`846`.
- Suppress REPL results returned by `pyodide.eval_code` by adding a semicolon
  {pr}`876`.
- Enable monkey patching of `eval_code` and `find_imports` to customize
  behavior of `runPython` and `runPythonAsync`
  {pr}`941`.

### Build system

- Updated docker image to Debian buster, resulting in smaller images.
  {pr}`815`
- Pre-built docker images are now available as
  [`iodide-project/pyodide`](https://hub.docker.com/r/iodide/pyodide)
  {pr}`787`
- Host Python is no longer compiled, reducing compilation time. This also
  implies that Python 3.8 is now required to build Pyodide. It can for instance
  be installed with conda.
  {pr}`830`
- FIX Infer package tarball directory from source URL
  {pr}`687`
- Updated to emscripten 1.38.44 and binaryen v86 (see related
  [commits](https://github.com/pyodide/pyodide/search?q=emscripten&type=commits))
- Updated default `--ldflags` argument to `pyodide_build` scripts to equal what
  Pyodide actually uses.
  {pr}`817`
- Replace C lz4 implementation with the (upstream) JavaScript implementation.
  {pr}`851`
- Pyodide deployment URL can now be specified with the `PYODIDE_BASE_URL`
  environment variable during build. The `pyodide_dev.js` is no longer
  distributed. To get an equivalent behavior with `pyodide.js`, set
  ```javascript
  window.languagePluginUrl = "./";
  ```
  before loading it.
  {pr}`855`
- Build runtime C libraries (e.g. libxml) via package build system with correct
  dependency resolution
  {pr}`927`
- Pyodide can now be built in a conda virtual environment
  {pr}`835`

### Other improvements

- Modify MEMFS timestamp handling to support better caching. This in
  particular allows to import newly created Python modules without invalidating
  import caches {pr}`893`

### Packages

- New packages: freesasa, lxml, python-sat, traits, astropy, pillow,
  scikit-image, imageio, numcodecs, msgpack, asciitree, zarr

  Note that due to the large size and the experimental state of the scipy
  package, packages that depend on scipy (including scikit-image, scikit-learn)
  will take longer to load, use a lot of memory and may experience failures.

- Updated packages: numpy 1.15.4, pandas 1.0.5, matplotlib 3.3.3 among others.
- New package
  [pyodide-interrupt](https://pypi.org/project/pyodide-interrupts/), useful for
  handling interrupts in Pyodide (see project description for details).

### Backward incompatible changes

- Dropped support for loading .wasm files with incorrect MIME type, following
  {pr}`851`

### List of contributors

abolger, Aditya Shankar, Akshay Philar, Alexey Ignatiev, Aray Karjauv, casatir,
chigozienri, Christian glacet, Dexter Chua, Frithjof, Hood Chatham, Jan Max
Meyer, Jay Harris, jcaesar, Joseph D. Long, Matthew Turk, Michael Greminger,
Michael Panchenko, mojighahar, Nicolas Ollinger, Ram Rachum, Roman Yurchak,
Sergio, Seungmin Kim, Shyam Saladi, smkm, Wei Ouyang

## Version 0.15.0

_May 19, 2020_

- Upgrades Pyodide to CPython 3.7.4.
- micropip no longer uses a CORS proxy to install pure Python packages from
  PyPI. Packages are now installed from PyPI directly.
- micropip can now be used from web workers.
- Adds support for installing pure Python wheels from arbitrary URLs with
  micropip.
- The CDN URL for Pyodide changed to
  https://pyodide-cdn2.iodide.io/v0.15.0/full/pyodide.js
  It now supports versioning and should provide faster downloads.
  The latest release can be accessed via
  https://pyodide-cdn2.iodide.io/latest/full/
- Adds `messageCallback` and `errorCallback` to
  `pyodide.loadPackage`.
- Reduces the initial memory footprint (`TOTAL_MEMORY`) from 1 GiB to 5 MiB.
  More memory will be allocated as needed.
- When building from source, only a subset of packages can be built by setting
  the `PYODIDE_PACKAGES` environment variable. See
  {ref}`partial builds documentation <partial-builds>` for more details.
- New packages: future, autograd

## Version 0.14.3

_Dec 11, 2019_

- Convert JavaScript numbers containing integers, e.g. `3.0`, to a real Python
  long (e.g. `3`).
- Adds `__bool__` method to for `JsProxy` objects.
- Adds a JavaScript-side auto completion function for Iodide that uses jedi.
- New packages: nltk, jeudi, statsmodels, regex, cytoolz, xlrd, uncertainties

## Version 0.14.0

_Aug 14, 2019_

- The built-in `sqlite` and `bz2` modules of Python are now enabled.
- Adds support for auto-completion based on jedi when used in iodide

## Version 0.13.0

_May 31, 2019_

- Tagged versions of Pyodide are now deployed to Netlify.

## Version 0.12.0

_May 3, 2019_

**User improvements:**

- Packages with pure Python wheels can now be loaded directly from PyPI. See
  `micropip` for more information.

- Thanks to PEP 562, you can now `import js` from Python and use it to access
  anything in the global JavaScript namespace.

- Passing a Python object to JavaScript always creates the same object in
  JavaScript. This makes APIs like `removeEventListener` usable.

- Calling `dir()` in Python on a JavaScript proxy now works.

- Passing an `ArrayBuffer` from JavaScript to Python now correctly creates a
  `memoryview` object.

- Pyodide now works on Safari.

## Version 0.11.0

_Apr 12, 2019_

**User improvements:**

- Support for built-in modules:

  - `sqlite`, `crypt`

- New packages: `mne`

**Developer improvements:**

- The `mkpkg` command will now select an appropriate archive to use, rather
  than just using the first.

- The included version of emscripten has been upgraded to 1.38.30 (plus a
  bugfix).

- New packages: `jinja2`, `MarkupSafe`

## Version 0.10.0

_Mar 21, 2019_

**User improvements:**

- New packages: `html5lib`, `pygments`, `beautifulsoup4`, `soupsieve`,
  `docutils`, `bleach`, `mne`

**Developer improvements:**

- `console.html` provides a simple text-only interactive console to test local
  changes to Pyodide. The existing notebooks based on legacy versions of Iodide
  have been removed.

- The `run_docker` script can now be configured with environment variables.

```{eval-rst}
.. toctree::
   :hidden:

   deprecation-timeline.md
```
