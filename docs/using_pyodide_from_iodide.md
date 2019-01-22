# Using Pyodide from Iodide

This document describes using Pyodide inside Iodide. For information
about using Pyodide directly from Javascript, see [Using Pyodide from
Javascript](using_pyodide_from_javascript.md).

## Running basic Python

Create a Python chunk, by inserting a line like this:

```
%% py
```

Type some Python code into the chunk, and press Shift+Enter to evaluate it. If
the last clause in the cell is an expression, that expression is evaluated,
converted to Javascript and displayed in the console like all other output
in Javascript. See [type conversions](type_conversions.md) for more information
about how data types are converted between Python and Javascript.

```python
%% py
import sys
sys.version
```

## Loading packages

Only the Python standard library and `six` are available after importing
Pyodide. Other available libraries, such as `numpy` and `matplotlib` are loaded
on demand.

If you just want to use the versions of those libraries included with Pyodide,
all you need to do is import and start using them:

```
%% py
import numpy as np
np.arange(10)
```

For most uses, that is all you need to know.

However, if you want to use your own custom package or load a package from
another provider, you'll need to use the `pyodide.loadPackage` function from a
Javascript chunk. For example, to load a special distribution of Numpy from
`custom.com`:

```
%% js
pyodide.loadPackage('https://custom.com/numpy.js')
```

After doing that, the numpy you import from a Python chunk will be this special
version of Numpy.
