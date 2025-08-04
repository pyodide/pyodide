(deprecation-timeline)=

# Pyodide Deprecation Timeline

Each Pyodide release may deprecate certain features from previous releases in a
backward incompatible way. If a feature is deprecated, it will continue to work
until its removal, but raise warnings. We try to ensure deprecations are done
over at least two minor(feature) releases, however, as Pyodide is still in beta
state, this list is subject to change and some features can be removed without
deprecation warnings. More details about each item can often be found in the
{ref}`changelog`.

## 0.25.0

- Typescript type imports for `PyProxy` subtypes from `pyodide` will be removed.

- The methods `PyProxy.supportsHas`, `PyProxy.isCallable`, etc will be removed.

- Support for the `homedir` argument will be removed in favor of
  `env: {HOME: "/the/home/directory"}`.

## 0.24.0

- The `messageCallback` and `errorCallback` argument to `loadPackage` and
  `loadPackagesFromImports` will be passed as a named argument only.

- `Py2JsResult` will be removed.

- The `--output-directory` argument to `pyodide build` will be removed.

## 0.23.0

- Names that used to be in the root `pyodide` module and were moved to submodules
  will no longer be available in the root module.
- The "message" argument to `PyProxy.destroy` method will no longer be accepted
  as a positional argument.

## 0.21.0

- The `globals` argument to `runPython` and `runPythonAsync` will be passed as a
  named argument only.
- The `extractDir` argument to `unpackArchive` will be passed as a named
  argument only.

## 0.20.0

- The skip-host key will be removed from the meta.yaml format. If needed,
  install a host copy of the package with pip instead.
- `pyodide-interrupts` module will be removed. If you were using this for some
  reason, use {js:func}`~pyodide.setInterruptBuffer` instead.

## 0.19.0

- The default working directory (home directory) inside the Pyodide virtual file
  system has been changed from `/` to `/home/pyodide`. To get the previous
  behavior, you can

  - call `os.chdir("/")` in Python to change working directory or
  - call {js:func}`~exports.loadPyodide` with the `homedir="/"`
    argument

- When a JavaScript function is called from Python, PyProxy arguments and return
  values will be automatically destroyed when the function is finished.
