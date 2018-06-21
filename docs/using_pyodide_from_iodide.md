# Using Pyodide from Iodide

This document describes using Pyodide inside Iodide. For information
about using Pyodide directly from Javascript, see [Using Pyodide from
Javascript](using_pyodide_from_javascript.md).

**NOTE:** The details of how this works on the Iodide side is likely to change
in the near future.

## Startup

The first step is to tell Iodide you want to import support for a new programming language.

Create a "language plugin cell" by selecting "plugin" from the cell type dropdown and insert the following JSON:

```json
{
  "languageId": "py",
  "displayName": "python",
  "codeMirrorMode": "python",
  "keybinding": "p",
  "url": "https://iodide.io/pyodide-demo/pyodide.js",
  "module": "pyodide",
  "evaluator": "runPython",
  "pluginType": "language"
}
```

Evaluate the cell (Shift+Enter) to load Pyodide and set up the Python environment.

## Running basic Python

Create a Python cell, by choosing Python from the cell type dropdown.

Insert some Python into the cell, and press Shift+Enter to evaluate it. If the
last clause in the cell is an expression, that expression is evaluated,
converted to Javascript and displayed in the output cell like all other output
in Javascript. See [type conversions](type_conversions.md) for more information
about how data types are converted between Python and Javascript.

```python
import sys
sys.version
```

## Loading packages

Only the Python standard library and `six` are available after importing
Pyodide. To use other libraries, you'll need to load their package using
`pyodide.loadPackage`. This is a Javascript API, so importantly, it must be run
from a Javascript cell. This downloads the file data over the network (as a
`.data` and `.js` index file) and installs the files in the virtual filesystem.

When you request a package, all of that package's dependencies are also loaded.

`pyodide.loadPackage` returns a `Promise`.

```javascript
pyodide.loadPackage('matplotlib')
```
