## Unreleased

- The built-in `sqlite` and `bz2` modules of Python are now enabled.

- New package: `nltk`

## Version 0.13.0

- Tagged versions of Pyodide are now deployed to Netlify.

## Version 0.12.0

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

**User improvements:**

- New packages: `html5lib`, `pygments`, `beautifulsoup4`, `soupsieve`,
  `docutils`, `bleach`, `mne`

**Developer improvements:**

- `console.html` provides a simple text-only interactive console to test local
  changes to Pyodide. The existing notebooks based on legacy versions of Iodide
  have been removed.

- The `run_docker` script can now be configured with environment variables.
