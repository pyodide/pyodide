## Unreleased

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
  `docutils`, `bleach`

**Developer improvements:**

- `console.html` provides a simple text-only interactive console to test local
  changes to Pyodide. The existing notebooks based on legacy versions of Iodide
  have been removed.

- The `run_docker` script can now be configured with environment variables.
