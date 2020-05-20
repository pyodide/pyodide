# Release notes

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
- Adds `messageCallback` and `errorCallback` to `pyodide.loadPackage`.
- Reduces the initial memory footprint (`TOTAL_MEMORY`) from 1 GiB to 5 MiB. More
  memory will be allocated as needed.
- When building from source, only a subset of packages can be built by setting
  the `PYODIDE_PACKAGES` environment variable. See
  [partial builds documentation](https://pyodide.readthedocs.io/en/latest/building_from_sources.html#partial-builds)
  for more details.
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
  `docs/pypi.md` for more information.

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
