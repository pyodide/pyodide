---
substitutions:
  API: "<span class='badge badge-warning'>API Change</span>"
  Enhancement : "<span class='badge badge-info'>Enhancement</span>"
  Feature : "<span class='badge badge-success'>Feature</span>"
  Fix : "<span class='badge badge-danger'>Fix</span>"
---


(changelog)=
# Change Log

## [Unreleased]

- {{ API }} {any}`pyodide.runPythonAsync` no longer automatically calls
  {any}`pyodide.loadPackagesFromImports`.
  {pr}`1538`.
- {{ Enhancement }} Added the {any}`PyProxy.callKwargs` method to allow using
  Python functions with keyword arguments from Javascript.
  {pr}`1539`
- {{ Enhancement }} Added the {any}`PyProxy.clone` method.
  {pr}`1549`

## Version 0.17.0
*April 21, 2020*

See the {ref}`0-17-0-release-notes` for more information.

### Improvements to package loading and dynamic linking
- {{ Enhancement }} Uses the emscripten preload plugin system to preload .so files in packages
- {{ Enhancement }} Support for shared library packages. This is used for CLAPACK which makes scipy a lot smaller.
  {pr}`1236`
- {{ Fix }} Pyodide and included packages can now be used with Safari v14+.
  Safari v13 has also been observed to work on some (but not all) devices.

### Python / JS type conversions
- {{ Feature }} A `JsProxy` of a Javascript `Promise` or other awaitable object is now a
  Python awaitable.
  {pr}`880`
- {{ API }} Instead of automatically converting Python lists and dicts into
  Javascript, they are now wrapped in `PyProxy`. Added a new {any}`PyProxy.toJs`
  API to request the conversion behavior that used to be implicit.
  {pr}`1167`
- {{ API }} Added {any}`JsProxy.to_py` API to convert a Javascript object to Python.
  {pr}`1244`
- {{ Feature }} Flexible jsimports: it now possible to add custom Python
  "packages" backed by Javascript code, like the `js` package.  The `js` package
  is now implemented using this system.
  {pr}`1146`
- {{ Feature }} A `PyProxy` of a Python coroutine or awaitable is now an
  awaitable Javascript object. Awaiting a coroutine will schedule it to run on
  the Python event loop using `asyncio.ensure_future`.
  {pr}`1170`
- {{ Enhancement }} Made `PyProxy` of an iterable Python object an iterable Js
  object: defined the `[Symbol.iterator]` method, can be used like `for(let x of
  proxy)`. Made a `PyProxy` of a Python iterator an iterator: `proxy.next()` is
  translated to `next(it)`. Made a `PyProxy` of a Python generator into a
  Javascript generator: `proxy.next(val)` is translated to `gen.send(val)`.
  {pr}`1180`
- {{ API }} Updated `PyProxy` so that if the wrapped Python object supports `__getitem__`
  access, then the wrapper has `get`, `set`, `has`, and `delete` methods which do
  `obj[key]`, `obj[key] = val`, `key in obj` and `del obj[key]` respectively.
  {pr}`1175`
- {{ API }} The {any}`pyodide.pyimport` function is deprecated in favor of using
  `pyodide.globals.get('key')`. {pr}`1367`
- {{ API }} Added {any}`PyProxy.getBuffer` API to allow direct access to Python
  buffers as Javascript TypedArrays.
  {pr}`1215`
- {{ API }} The innermost level of a buffer converted to Javascript used to be a
  TypedArray if the buffer was contiguous and otherwise an Array. Now the
  innermost level will be a TypedArray unless the buffer format code is a '?' in
  which case it will be an Array of booleans, or if the format code is a "s" in
  which case the innermost level will be converted to a string.
  {pr}`1376`
- {{ Enhancement }} Javascript `BigInt`s are converted into Python `int` and
  Python `int`s larger than 2^53 are converted into `BigInt`.
  {pr}`1407`
- {{ API }} Added {any}`pyodide.isPyProxy` to test if an object is a `PyProxy`.
  {pr}`1456`
- {{ Enhancement }} `PyProxy` and `PyBuffer` objects are now garbage collected
  if the browser supports `FinalizationRegistry`.
  {pr}`1306`
- {{ Enhancement }} Automatic conversion of Javascript functions to CPython
  calling conventions.
  {pr}`1051`, {pr}`1080`
- {{ Enhancement }} Automatic detection of fatal errors. In this case Pyodide
  will produce both a Javascript and a Python stack trace with explicit
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
- {{ Fix }} When calling a Javascript function from Python without keyword
  arguments, Pyodide no longer passes a `PyProxy`-wrapped `NULL` pointer as the
  last argument. {pr}`1033`
- {{ Fix }} JsBoundMethod is now a subclass of JsProxy, which fixes nested
  attribute access and various other strange bugs.
  {pr}`1124`
- {{ Fix }} Javascript functions imported like `from js import fetch` no longer
  trigger "invalid invocation" errors (issue {issue}`461`) and
  `js.fetch("some_url")` also works now (issue {issue}`768`).
  {pr}`1126`
- {{ Fix }} Javascript bound method calls now work correctly with keyword arguments.
  {pr}`1138`
- {{ Fix }} Javascript constructor calls now work correctly with keyword
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
  `SharedArrayBuffer` to be the keyboard interupt buffer. If Pyodide is running
  on a webworker, the main thread can signal to the webworker that it should
  raise a `KeyboardInterrupt` by writing to the interrupt buffer.
  {pr}`1148` and {pr}`1173`
- Changed the loading method: added an async function `loadPyodide` to load
  Pyodide to use instead of `languagePluginURL` and `languagePluginLoader`. The
  change is currently backwards compatible, but the old approach is deprecated.
  {pr}`1363`

### micropip

- {{ Feature }} `micropip` now supports installing wheels from relative URLs.
  {pr}`872`
- {{ API }} `micropip.install` now returns a Python `Future` instead of a Javascript `Promise`.
  {pr}`1324`
- {{ FIX }} {any}`micropip.install` now interacts correctly with
  {any}`pyodide.loadPackage`.
  {pr}`1457`
- {{ FIX }} {any}`micropip.install` now handles version constraints correctly
  even if there is a version of the package available from the Pyodide `indexURL`.


### Build system

- {{ Enhancement }} Updated to latest emscripten 2.0.13 with the updstream LLVM backend
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

## List of contributors

(in alphabetic order)

Aditya Shankar, casatir, Dexter Chua, dmondev, Frederik Braun, Hood Chatham,
Jan Max Meyer, Jeremy Tuloup, joemarshall, leafjolt, Michael Greminger,
Mireille Raad, Ondřej Staněk, Paul m. p. P, rdb, Roman Yurchak, Rudolfs

## Version 0.16.1
*December 25, 2020*

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
- Javascript exceptions can now be raised and caught in Python. They are
  wrapped in pyodide.JsException.
  {pr}`891`

### pyodide-py package and micropip

- The `pyodide.py` file was transformed to a pyodide-py package. The imports
  remain the same so this change is transparent to the users
  {pr}`909`.
- FIX Get last version from PyPi when installing a module via micropip
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
- Replace C lz4 implementation with the (upstream) Javascript implementation.
  {pr}`851`
- Pyodide deployment URL can now be specified with the `PYODIDE_BASE_URL`
  environment variable during build. The `pyodide_dev.js` is no longer
  distributed. To get an equivalent behavior with `pyodide.js`, set
  ```javascript
  window.languagePluginUrl = './';
  ```
  before loading it.
  {pr}`855`
- Build runtime C libraries (e.g. libxml) via package build system with correct
  dependency resolution
  {pr}`927`
- Pyodide can now be built in a conda virtual environment
  {pr}`835`

### Other improvements

- Modifiy MEMFS timestamp handling to support better caching. This in
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
*May 19, 2020*

- Upgrades Pyodide to CPython 3.7.4.
- micropip no longer uses a CORS proxy to install pure Python packages from
  PyPi. Packages are now installed from PyPi directly.
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
*Dec 11, 2019*

- Convert Javascript numbers containing integers, e.g. `3.0`, to a real Python
  long (e.g. `3`).
- Adds `__bool__` method to for `JsProxy` objects.
- Adds a Javascript-side auto completion function for Iodide that uses jedi.
- New packages: nltk, jeudi, statsmodels, regex, cytoolz, xlrd, uncertainties

## Version 0.14.0
*Aug 14, 2019*

- The built-in `sqlite` and `bz2` modules of Python are now enabled.
- Adds support for auto-completion based on jedi when used in iodide

## Version 0.13.0
*May 31, 2019*

- Tagged versions of Pyodide are now deployed to Netlify.

## Version 0.12.0
*May 3, 2019*

**User improvements:**

- Packages with pure Python wheels can now be loaded directly from PyPI. See
  {ref}`micropip` for more information.

- Thanks to PEP 562, you can now `import js` from Python and use it to access
  anything in the global Javascript namespace.

- Passing a Python object to Javascript always creates the same object in
  Javascript. This makes APIs like `removeEventListener` usable.

- Calling `dir()` in Python on a Javascript proxy now works.

- Passing an `ArrayBuffer` from Javascript to Python now correctly creates a
  `memoryview` object.

- Pyodide now works on Safari.

## Version 0.11.0
*Apr 12, 2019*

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
*Mar 21, 2019*

**User improvements:**

- New packages: `html5lib`, `pygments`, `beautifulsoup4`, `soupsieve`,
  `docutils`, `bleach`, `mne`

**Developer improvements:**

- `console.html` provides a simple text-only interactive console to test local
  changes to Pyodide. The existing notebooks based on legacy versions of Iodide
  have been removed.

- The `run_docker` script can now be configured with environment variables.
