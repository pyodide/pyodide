---
substitutions:
  API: "<span class='badge badge-warning'>API Change</span>"
  Enhancement: "<span class='badge badge-info'>Enhancement</span>"
  Feature: "<span class='badge badge-success'>Feature</span>"
  Fix: "<span class='badge badge-danger'>Fix</span>"
  Update: "<span class='badge badge-success'>Update</span>"
  Breaking: "<span class='badge badge-danger'>BREAKING CHANGE</span>"
---

(changelog)=

# Change Log

## Unreleased

- {{ Fix }} `micropip` supports extra markers in packages correctly now.
  {pr}`2584`
- {{ Enhancement }} Integrity of Pyodide packages are now verified before
  loading them. This is for now only limited to browser environments.
  {pr}`2513`

- {{ Fix }} Fix building on macOS {issue}`2360` {pr}`2554`

- {{ Fix }} Fix a REPL error in printing high-dimensional lists.
  {pr}`2517`

- {{ Fix }} Fix output bug with using `input()` on online console
  {pr}`2509`

- {{ Enhancement }} Update sqlite version to latest stable release
  {pr}`2477` and {pr}`2518`

- {{ Fix }} We now tell packagers (e.g., Webpack) to ignore npm-specific imports
  when packing files for the browser.
  {pr}`2468`

- {{ Enhancement }} Update Typescript target to ES2017 to generate more modern
  Javascript code.
  {pr}`2471`

- {{ Enhancement }} We now put our built files into the `dist` directory rather
  than the `build` directory. {pr}`2387`

- {{ Enhancement }} `loadPyodide` no longer uses any global state, so it can be
  used more than once in the same thread. This is recommended if a network
  request causes a loading failure, if there is a fatal error, if you damage the
  state of the runtime so badly that it is no longer usable, or for certain
  testing purposes. It is not recommended for creating multiple execution
  environments, for which you should use
  `pyodide.runPython(code, { globals : some_dict})`;
  {pr}`2391`

- {{ Fix }} The build will error out earlier if `cmake` or `libtool` are not
  installed.
  {pr}`2423`

- {{ Enhancement }} `pyodide.unpackArchive` now accepts any `ArrayBufferView` or
  `ArrayBuffer` as first argument, rather than only a `Uint8Array`.
  {pr}`2451`

- {{ Feature }} Added `pyodide.run_js` API.
  {pr}`2426`

- {{ Enhancement }} Add SHA-256 hash of package to entries in `packages.json`
  {pr}`2455`

- {{ Fix }} BigInt's between 2^{32\*n - 1} and 2^{32\*n} no longer get
  translated to negative Python ints.
  {pr}`2484`

- {{ Fix }} Pyodide now correctly handles JavaScript objects with `null`
  constructor.
  {pr}`2520`

- {{ Fix }} Fix garbage collection of `once_callable` {pr}`2401`

- {{ Enhancement }} `run_in_pyodide` now has support for pytest assertion
  rewriting and decorators such as `pytest.mark.parametrize` and hypothesis.
  {pr}`2510`, {pr}`2541`

- {{ Breaking }} `pyodide_build.testing` is removed. `run_in_pyodide`
  decorator can now be accessed through `pyodide_test_runner`.
  {pr}`2418`

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

- {{ Enhancement }} Pyodide now directly exposes the Emscripten `PATH` and
  `ERRNO_CODES` APIs.
  {pr}`2582`

- {{ Fix }} If the request errors due to CORS, `pyfetch` now raises an `OSError`
  not a `JSException`.
  {pr}`2598`

- {{ Enhancement }} The platform tags of wheels now include the Emscripten
  version in them. This should help ensure ABI compatibility if Emscripten
  wheels are distributed outside of the main Pyodide distribution.
  {pr}`2610`

- {{ Enhancement }} The build system now uses the sysconfigdata from the target
  Python rather than the host Python.
  {pr}`2516`

- {{ Enhancement }} Pyodide now builds with `-sWASM_BIGINT`..
  {pr}`2643`

### REPL

- {{ Enhancement }} Add a spinner while the REPL is loading
  {pr}`2635`

- {{ Enhancement }} Cursor blinking in the REPL can be disabled by setting
  `noblink` in URL search params.
  {pr}`2666`

### micropip

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
  packages into a `packages.json` file.
  {pr}`2581`

### Packages

- {{ Enhancement }} Pillow now supports WEBP image format {pr}`2407`.

- Pandas is now compiled with `-Oz`, which significantly speeds up loading the library
  on Chrome {pr}`2457`

- New packages: opencv-python v4.5.5.64 {pr}`2305`, ffmpeg {pr}`2305`, libwebp {pr}`2305`,
  h5py, pkgconfig and libhdf5 {pr}`2411`, bitarray {pr}`2459`, gsw {pr}`2511`, cftime {pr}`2504`,
  svgwrite, jsonschema, tskit {pr}`2506`, xarray {pr}`2538`, demes, libgsl, newick,
  ruamel, msprime {pr}`2548`, gmpy2 {pr}`2665`, xgboost {pr}`2537`, galpy {pr}`2676`.

## Version 0.20.0

[See the release notes for a summary.](https://blog.pyodide.org/posts/0.20-release/)

### CPython and stdlib

- {{ Update }} Pyodide now runs Python 3.10.2.
  {pr}`2225`

- {{ Enhancement }} All
  `ctypes` tests pass now except for `test_callback_too_many_args` (and we have
  a plan to fix `test_callback_too_many_args` upstream). `libffi-emscripten`
  now also passes all libffi tests.
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
  {any}`setInterruptBuffer <pyodide.setInterruptBuffer>` instead.
  {pr}`2309`

- Most included packages were updated to the latest version. See
  {ref}`packages-in-pyodide` for a full list.

### Type translations

- {{Fix}} Python tracebacks now include Javascript frames when Python calls a
  Javascript function.
  {pr}`2123`

- {{Enhancement}} Added a `default_converter` argument to {any}`JsProxy.to_py`
  and {any}`pyodide.toPy` which is used to process any object that doesn't have
  a built-in conversion to Python. Also added a `default_converter` argument to
  {any}`PyProxy.toJs` and {any}`pyodide.to_js` to convert.
  {pr}`2170` and {pr}`2208`

- {{ Enhancement }} Async Python functions called from Javascript now have the
  resulting coroutine automatically scheduled. For instance, this makes it
  possible to use an async Python function as a Javascript event handler.
  {pr}`2319`

### Javascript package

- {{Enhancement}} It is no longer necessary to provide `indexURL` to
  {any}`loadPyodide <globalThis.loadPyodide>`.
  {pr}`2292`

- {{ Breaking }} The `globals` argument to {any}`runPython <pyodide.runPython>`
  and {any}`runPythonAsync <pyodide.runPythonAsync>` is now passed as a named
  argument. The old usage still works with a deprecation warning.
  {pr}`2300`

- {{Enhancement}} The Javascript package was migrated to Typescript.
  {pr}`2130` and {pr}`2133`

- {{Fix}} Fix importing pyodide with ESM syntax in a module type web worker.
  {pr}`2220`

- {{Enhancement}} When Pyodide is loaded as an ES6 module, no global
  {any}`loadPyodide <globalThis.loadPyodide>` variable is created (instead, it
  should be accessed as an attribute on the module).
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

- {{ Breaking }} The `extractDir` argument to
  {any}`unpackArchive <pyodide.unpackArchive>` is now passed as a named argument.
  The old usage still works with a deprecation warning.
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

- {{Enhancement}} Added the {any}`pyodide.http.pyfetch` API which provides a
  convenience wrapper for the Javascript `fetch` API. The API returns a response
  object with various methods that convert the data into various types while
  minimizing the number of times the data is copied.
  {pr}`1865`

- {{Enhancement}} Added the {any}`unpack_archive` API to the {any}`FetchResponse`
  object which treats the response body as an archive and uses `shutil` to
  unpack it. {pr}`1935`

- {{Fix}} The Pyodide event loop now works correctly with cancelled handles. In
  particular, `asyncio.wait_for` now functions as expected.
  {pr}`2022`

### JavaScript package

- {{Fix}} {any}`loadPyodide <globalThis.loadPyodide>` no longer fails in the
  presence of a user-defined global named `process`.
  {pr}`1849`

- {{Fix}} Various webpack buildtime and runtime compatibility issues were fixed.
  {pr}`1900`

- {{Enhancement}} Added the {any}`pyodide.pyimport` API to import a Python module
  and return it as a `PyProxy`. Warning: this is different from the
  original `pyimport` API which was removed in this version.
  {pr}`1944`

- {{Enhancement}} Added the {any}`pyodide.unpackArchive` API which unpacks an
  archive represented as an ArrayBuffer into the working directory. This is
  intended as a way to install packages from a local application.
  {pr}`1944`

- {{API}} {any}`loadPyodide <globalThis.loadPyodide>` now accepts a `homedir`
  parameter which sets home directory of Pyodide virtual file system.
  {pr}`1936`

- {{Breaking}} The default working directory(home directory) inside the Pyodide
  virtual file system has been changed from `/` to `/home/pyodide`. To get the
  previous behavior, you can
  - call `os.chdir("/")` in Python to change working directory or
  - call {any}`loadPyodide <globalThis.loadPyodide>` with the `homedir="/"`
    argument
    {pr}`1936`

### Python / JavaScript type conversions

- {{Breaking}} Updated the calling convention when a JavaScript function is
  called from Python to improve memory management of PyProxies. PyProxy
  arguments and return values are automatically destroyed when the function is
  finished.
  {pr}`1573`

- {{Enhancement}} Added {any}`JsProxy.to_string`, {any}`JsProxy.to_bytes`, and
  {any}`JsProxy.to_memoryview` to allow for conversion of `TypedArray` to
  standard Python types without unneeded copies. {pr}`1864`

- {{Enhancement}} Added {any}`JsProxy.to_file` and {any}`JsProxy.from_file` to
  allow reading and writing Javascript buffers to files as a byte stream without
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

- {{Fix}} The {any}`pyodide.setInterruptBuffer` command is now publicly exposed
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

  They are loaded by default in {any}`loadPyodide <globalThis.loadPyodide>`, however this behavior
  can be disabled with the `fullStdLib` parameter set to `false`.
  All optional stdlib modules can then be loaded as needed with
  {any}`pyodide.loadPackage`. {pr}`1543`

- {{ Enhancement }} The standard library module `audioop` is now included, making the `wave`,
  `sndhdr`, `aifc`, and `sunau` modules usable. {pr}`1623`

- {{ Enhancement }} Added support for `ctypes`.
  {pr}`1656`

### JavaScript package

- {{ Enhancement }} The Pyodide JavaScript package is released to npm under [npmjs.com/package/pyodide](https://www.npmjs.com/package/pyodide)
  {pr}`1762`
- {{ API }} {any}`loadPyodide <globalThis.loadPyodide>` no longer automatically
  stores the API into a global variable called `pyodide`. To get old behavior,
  say `globalThis.pyodide = await loadPyodide({...})`.
  {pr}`1597`
- {{ Enhancement }} {any}`loadPyodide <globalThis.loadPyodide>` now accepts callback functions for
  `stdin`, `stdout` and `stderr`
  {pr}`1728`
- {{ Enhancement }} Pyodide now ships with first party typescript types for the entire
  JavaScript API (though no typings are available for `PyProxy` fields).
  {pr}`1601`

- {{ Enhancement }} It is now possible to import `Comlink` objects into Pyodide after
  using {any}`pyodide.registerComlink`
  {pr}`1642`

- {{ Enhancement }} If a Python error occurs in a reentrant `runPython` call, the error
  will be propagated into the outer `runPython` context as the original error
  type. This is particularly important if the error is a `KeyboardInterrupt`.
  {pr}`1447`

### Python package

- {{ Enhancement }} Added a new {any}`CodeRunner` API for finer control than
  {any}`eval_code` and {any}`eval_code_async`. Designed with
  the needs of REPL implementations in mind.
  {pr}`1563`

- {{ Enhancement }} Added {any}`Console` class closely based on the Python standard
  library `code.InteractiveConsole` but with support for top level await and
  stream redirection. Also added the subclass {any}`PyodideConsole` which
  automatically uses {any}`pyodide.loadPackagesFromImports` on the code before running
  it.
  {pr}`1125`, {pr}`1155`, {pr}`1635`

- {{ Fix }} {any}`eval_code_async` no longer automatically awaits a returned
  coroutine or attempts to await a returned generator object (which triggered an
  error).
  {pr}`1563`

### Python / JavaScript type conversions

- {{ API }} {any}`pyodide.runPythonAsync` no longer automatically calls
  {any}`pyodide.loadPackagesFromImports`.
  {pr}`1538`.
- {{ Enhancement }} Added the {any}`PyProxy.callKwargs` method to allow using
  Python functions with keyword arguments from JavaScript.
  {pr}`1539`
- {{ Enhancement }} Added the {any}`PyProxy.copy` method.
  {pr}`1549` {pr}`1630`
- {{ API }} Updated the method resolution order on `PyProxy`. Performing a
  lookup on a `PyProxy` will prefer to pick a method from the `PyProxy` api, if
  no such method is found, it will use `getattr` on the proxied object.
  Prefixing a name with `$` forces `getattr`. For instance, {any}`PyProxy.destroy`
  now always refers to the method that destroys the proxy, whereas
  `PyProxy.$destroy` refers to an attribute or method called `destroy` on the
  proxied object.
  {pr}`1604`
- {{ API }} It is now possible to use `Symbol` keys with PyProxies. These
  `Symbol` keys put markers on the PyProxy that can be used by external code.
  They will not currently be copied by {any}`PyProxy.copy`.
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
- {{ API }} {any}`toJs <PyProxy.toJs>` and {any}`to_js <pyodide.to_js>` now
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
  JavaScript, they are now wrapped in `PyProxy`. Added a new {any}`PyProxy.toJs`
  API to request the conversion behavior that used to be implicit.
  {pr}`1167`
- {{ API }} Added {any}`JsProxy.to_py` API to convert a JavaScript object to Python.
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
  object: defined the `[Symbol.iterator]` method, can be used like `for(let x of proxy)`. Made a `PyProxy` of a Python iterator an iterator: `proxy.next()` is
  translated to `next(it)`. Made a `PyProxy` of a Python generator into a
  JavaScript generator: `proxy.next(val)` is translated to `gen.send(val)`.
  {pr}`1180`
- {{ API }} Updated `PyProxy` so that if the wrapped Python object supports `__getitem__`
  access, then the wrapper has `get`, `set`, `has`, and `delete` methods which do
  `obj[key]`, `obj[key] = val`, `key in obj` and `del obj[key]` respectively.
  {pr}`1175`
- {{ API }} The `pyodide.pyimport` function is deprecated in favor of using
  `pyodide.globals.get('key')`. {pr}`1367`
- {{ API }} Added {any}`PyProxy.getBuffer` API to allow direct access to Python
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
- {{ API }} Added {any}`pyodide.isPyProxy` to test if an object is a `PyProxy`.
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
- {{ Fix }} {any}`micropip.install` now interacts correctly with
  {any}`pyodide.loadPackage`.
  {pr}`1457`
- {{ Fix }} {any}`micropip.install` now handles version constraints correctly
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
  {any}`pyodide.loadPackage`.
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
  {ref}`micropip` for more information.

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
