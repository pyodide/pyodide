# Using Pyodide from Javascript

This document describes using Pyodide directly from Javascript. For information
about using Pyodide from Iodide, see [Using Pyodide from
Iodide](using_pyodide_from_iodide.md).

## Startup

Include `pyodide.js` in your project.

This has a single function which bootstraps the Python environment:
`languagePluginLoader`. Since this must happen asynchronously, it returns a
`Promise`, which you must call `then` on to complete initialization. When the
promise resolves, pyodide will have installed a namespace in global scope:
`pyodide`.

```javascript
languagePluginLoader.then(() => {
  // pyodide is now ready to use...
  console.log(pyodide.runPython('import sys\nsys.version'));
});
```

## Running Python code

Python code is run using the `pyodide.runPython` function. It takes as input a
string of Python code. If the code ends in an expression, it returns the result
of the expression, converted to Javascript objects (See [type
conversions](type_conversions.md)).

```javascript
pyodide.runPython('import sys\nsys.version'));
```

## Loading packages

Only the Python standard library and `six` are available after importing
Pyodide. To use other libraries, you'll need to load their package using
`pyodide.loadPackage`. This downloads the file data over the network (as a
`.data` and `.js` index file) and installs the files in the virtual filesystem.

When you request a package, all of that package's dependencies are also loaded.

`pyodide.loadPackage` returns a `Promise`.

```javascript
pyodide.loadPackage('matplotlib').then(() => {
  // matplotlib is not available
});
```

## Complete example

TODO
