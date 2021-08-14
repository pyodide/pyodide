# Pyodide Javascript package

<a href="https://www.npmjs.com/package/pyodide"><img src="https://img.shields.io/npm/v/pyodide" alt="npm"></a>

## Usage

Download and extract Pyodide packages from [Github
releases](https://github.com/pyodide/pyodide/releases)
(`pyodide-build-*.tar.bz2`). The version of the release needs to match exactly the version of this package.

Then you can load Pyodide in Node.js as follows,

```js
let pyodide_pkg = await import("pyodide/pyodide.js");

let pyodide = await pyodide_pkg.loadPyodide({
  indexURL: "<pyodide artifacts folder>",
});

await pyodide.runPythonAsync("1+1");
```

**Note**: To start node REPL with support for top level await, use `node --experimental-repl-await`.

See the [documentation](https://pyodide.org/en/stable/) fore more details.

## Details

The Javascript code in this package is responsible for the following tasks:

1. Defines the public [Javascript API](https://pyodide.org/en/stable/usage/api/js-api.html)
   - Package loading code to allow loading of other Python packages.
   - Can load
     [micropip](https://pyodide.org/en/stable/usage/api/micropip-api.html) to
     bootstrap loading of pure Python wheels
2. Loads the CPython interpreter and the core/pyodide emscripten application
   which embeds the interpreter.
3. Injects the `js/pyodide` Javascript API into `sys.modules`. This is the
   final runtime dependency for `core/pyodide` & `py/pyodide`, so after this step
   the interpreter is fully up and running.
