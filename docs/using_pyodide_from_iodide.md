# Using Pyodide from Iodide

This document describes using Pyodide inside Iodide. For information
about using Pyodide directly from Javascript, see [Using Pyodide from
Javascript](using_pyodide_from_javascript.md).

## Running basic Python

Create a Python chunk, by inserting a line like this:

```python
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

```python
%% py
import numpy as np
np.arange(10)
```

For most uses, that is all you need to know.

However, if you want to use your own custom package or load a package from
another provider, you'll need to use the `pyodide.loadPackage` function from a
Javascript chunk. For example, to load a special distribution of Numpy from
`custom.com`:

```js
%% js
pyodide.loadPackage('https://custom.com/numpy.js')
```

After doing that, the numpy you import from a Python chunk will be this special
version of Numpy.

## Using a local build of Pyodide with Iodide

You may want to build a local copy of Pyodide with some changes and test it
inside of Iodide.

By default, Iodide will use a copy of Pyodide deployed to Netlify. However, it
will use locally-installed copy of Pyodide if `USE_LOCAL_PYODIDE` is set.

Set that environment variable in your shell:

```bash
export USE_LOCAL_PYODIDE=1
```

Then follow the building and running instructions for Iodide as usual.

Next, build Pyodide using the regular instructions in `../README.md`. Copy the
contents of Pyodide's build directory to your Iodide checkout's `build/pyodide`
directory:

```bash
mkdir $IODIDE_CHECKOUT/build/pyodide
cp $PYODIDE_CHECKOUT/build/* $IODIDE_CHECKOUT/build/pyodide
```
