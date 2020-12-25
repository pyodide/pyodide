(changelog)=
# Release notes

## Version 0.16.1
*December 25, 2020*

Note: due to a CI deployment issue the 0.16.0 release was skipped and replaced
by 0.16.1 with identical contents.

- Pyodide files are distributed by [JsDelivr](https://www.jsdelivr.com/),
  `https://cdn.jsdelivr.net/pyodide/v0.16.1/full/pyodide.js`
  The previous CDN `pyodide-cdn2.iodide.io` still works and there
  are no plans for deprecating it. However please use
  JsDelivr as a more sustainable solution, including for earlier pyodide
  versions.

### Python and the standard library

- Pyodide includes CPython 3.8.2
  [#712](https://github.com/iodide-project/pyodide/pull/712)
- ENH Patches for the threading module were removed in all packages.
  Importing the module, and a subset of functionality (e.g. locks) works,
  while starting a new thread will produce an exception, as expected.
  [#796](https://github.com/iodide-project/pyodide/pull/796). See
  [#237](https://github.com/iodide-project/pyodide/pull/237) for the current
  status of the threading support.
- ENH The multiprocessing module is now included, and will not fail at import,
  thus avoiding the necessity to patch included packages. Starting a new process
  will produce an exception due to the limitation of the WebAssembly VM  with
  the following message: `Resource temporarily unavailable`
  [#796](https://github.com/iodide-project/pyodide/pull/796).

### Python / JS type conversions

- FIX Only call `Py_INCREF()` once when proxied by PyProxy
  [#708](https://github.com/iodide-project/pyodide/pull/708)
- Javascript exceptions can now be raised and caught in Python. They are
  wrapped in pyodide.JsException.
  [#891](https://github.com/iodide-project/pyodide/pull/891)

### pyodide-py package and micropip

- The `pyodide.py` file was transformed to a pyodide-py package. The imports
  remain the same so this change is transparent to the users
  [#909](https://github.com/iodide-project/pyodide/pull/909).
- FIX Get last version from PyPi when installing a module via micropip
  [#846](https://github.com/iodide-project/pyodide/pull/846).
- Suppress REPL results returned by `pyodide.eval_code` by adding a semicolon
  [#876](https://github.com/iodide-project/pyodide/pull/876).
- Enable monkey patching of `eval_code` and `find_imports` to customize behavior
  of `runPython` and `runPythonAsync`
  [#941](https://github.com/iodide-project/pyodide/pull/941).

### Build system

- Updated docker image to Debian buster, resulting in smaller images.
  [#815](https://github.com/iodide-project/pyodide/pull/815)
- Pre-built docker images are now available as
  [`iodide-project/pyodide`](https://hub.docker.com/r/iodide/pyodide)
  [#787](https://github.com/iodide-project/pyodide/pull/787)
- Host python is no longer compiled, reducing compilation time. This also
  implies that python 3.8 is now required to build pyodide. It can for instance
  be installed with conda.
  [#830](https://github.com/iodide-project/pyodide/pull/830)
- FIX Infer package tarball directory from source url
  [#687](https://github.com/iodide-project/pyodide/pull/687)
- Updated to emscripten 1.38.44 and binaryen v86
  (see related [commits](https://github.com/iodide-project/pyodide/search?q=emscripten&type=commits))
- Updated default `--ldflags` argument to `pyodide_build` scripts to equal what
  pyodide actually uses.
  [#817](https://github.com/iodide-project/pyodide/pull/480)
- Replace C lz4 implementation with the (upstream) Javascript implementation.
  [#851](https://github.com/iodide-project/pyodide/pull/851)
- Pyodide deployment URL can now be specified with the `PYODIDE_BASE_URL`
  environment variable during build. The `pyodide_dev.js` is no longer distributed.
  To get an equivalent behavior with `pyodide.js`, set,
  ```
  window.languagePluginUrl = './';
  ```
  before loading it.
  [#855](https://github.com/iodide-project/pyodide/pull/855)
- Build runtime C libraries (e.g. libxml) via package build system with correct
  dependency resolution
  [#927](https://github.com/iodide-project/pyodide/pull/927)
- Pyodide can now be built in a conda virtual environment
  [#835](https://github.com/iodide-project/pyodide/pull/835)

### Other improvements

- Modifiy MEMFS timestamp handling to support better caching. This in particular allows to
  import newly created python modules without invalidating import caches
  [#893](https://github.com/iodide-project/pyodide/pull/893)

### Packages
- New packages: freesasa, lxml, python-sat, traits, astropy, pillow,
  scikit-image, imageio, numcodecs, msgpack, asciitree, zarr

  Note that due to the large size and the experimental state of the scipy
  package, packages that depend on scipy (including scikit-image, scikit-learn)
  will take longer to load, use a lot of memory and may experience failures.

- Updated packages: numpy 1.15.4, pandas 1.0.5, matplotlib 3.3.3 among others.
- New package
  [pyodide-interrupt](https://pypi.org/project/pyodide-interrupts/), useful for
  handling interrupts in Pyodide (see project descripion for details).


### Backward incompatible changes

- Dropped support for loading .wasm files with incorrect MIME type, following
  [#851](https://github.com/iodide-project/pyodide/pull/851)


### List of contributors

abolger, Aditya Shankar, Akshay Philar, Alexey Ignatiev, Aray Karjauv, casatir,
chigozienri, Christian glacet, Dexter Chua, Frithjof, Hood Chatham, Jan Max
Meyer, Jay Harris, jcaesar, Joseph D. Long, Matthew Turk, Michael Greminger,
Michael Panchenko, mojighahar, Nicolas Ollinger, Ram Rachum, Roman Yurchak,
Sergio, Seungmin Kim, Shyam Saladi, smkm, Wei Ouyang

## Version 0.15.0
*May 19, 2020*

- Upgrades pyodide to CPython 3.7.4.
- micropip no longer uses a CORS proxy to install pure Python packages from
  PyPi. Packages are now installed from PyPi directly.
- micropip can now be used from web workers.
- Adds support for installing pure Python wheels from arbitrary URLs with micropip.
- The CDN URL for pyodide changed to
  https://pyodide-cdn2.iodide.io/v0.15.0/full/pyodide.js
  It now supports versioning and should provide faster downloads. The latest release
  can be accessed via `https://pyodide-cdn2.iodide.io/latest/full/`
- Adds `messageCallback` and `errorCallback` to
  {ref}`pyodide.loadPackage <js_api_pyodide_loadPackage>`.
- Reduces the initial memory footprint (`TOTAL_MEMORY`) from 1 GiB to 5 MiB. More
  memory will be allocated as needed.
- When building from source, only a subset of packages can be built by setting
  the `PYODIDE_PACKAGES` environment variable. See
  {ref}`partial builds documentation <partial-builds>` for more details.
- New packages: future, autograd

## Version 0.14.3
*Dec 11, 2019*

- Convert JavaScript numbers containing integers, e.g. `3.0`, to a real Python
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

- Calling `dir()` in Python on a JavaScript proxy now works.

- Passing an `ArrayBuffer` from Javascript to Python now correctly creates
  a `memoryview` object.

- Pyodide now works on Safari.

## Version 0.11.0
*Apr 12, 2019*

**User improvements:**

- Support for built-in modules:
  - `sqlite`, `crypt`

- New packages: `mne`

**Developer improvements:**

- The `mkpkg` command will now select an appropriate archive to use, rather than
  just using the first.

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
