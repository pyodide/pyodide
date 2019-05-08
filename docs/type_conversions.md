# Type conversions

Python to Javascript conversions occur:

- when returning the final expression from a `pyodide.runPython` call (evaluating a Python cell in Iodide)
- using `pyodide.pyimport`
- passing arguments to a Javascript function from Python

Javascript to Python conversions occur:

- when using the `from js import ...` syntax
- returning the result of a Javascript function to Python

## Basic types

The following basic types are implicitly converted between Javascript and
Python. The values are copied and any connection to the original object is lost.

| Python          | Javascript          |
|-----------------|---------------------|
| `int`, `float`  | `Number`            |
| `str`           | `String`            |
| `True`          | `true`              |
| `False`         | `false`             |
| `None`          | `undefined`, `null` |
| `list`, `tuple` | `Array`             |
| `dict`          | `Object`            |

## Typed arrays

Javascript typed arrays (Int8Array and friends) are converted to Python
`memoryviews`. This happens with a single binary memory copy (since Python can't
access arrays on the Javascript heap), and the data type is preserved. This
makes it easy to correctly convert it to a Numpy array using `numpy.asarray`:

```javascript
array = Float32Array([1, 2, 3])
```

```python
from js import array
import numpy as np
numpy_array = np.asarray(array)
```

Python `bytes` and `buffer` objects are converted to Javascript as
`Uint8ClampedArray`s, without any memory copy at all, and is thus very
efficient, but be aware that any changes to the buffer will be reflected in both
places.

Numpy arrays are currently converted to Javascript as nested (regular) Arrays. A
more efficient method will probably emerge as we decide on an ndarray
implementation for Javascript.

## Class instances

Any of the types not listed above are shared between languages using proxies
that allow methods and some operators to be called on the object from the other
language.

### Javascript from Python

When passing a Javascript object to Python, an extension type is used to
delegate Python operations to the Javascript side. The following operations are
currently supported. (More should be possible in the future -- work in ongoing
to make this more complete):

| Python         | Javascript      |
|----------------|-----------------|
| `repr(x)`      | `x.toString()`  |
| `x.foo`        | `x.foo`         |
| `x.foo = bar`  | `x.foo = bar`   |
| `del x.foo`    | `delete x.foo`  |
| `x(...)`       | `x(...)`        |
| `x.foo(...)`   | `x.foo(...)`    |
| `X.new(...)`   | `new X(...)`    |
| `len(x)`       | `x.length`      |
| `x[foo]`       | `x[foo]`        |
| `x[foo] = bar` | `x[foo] = bar`  |
| `del x[foo]`   | `delete x[foo]` |
| `x == y`       | `x == y`        |
| `x.typeof`     | `typeof x`      |

One important difference between Python objects and Javascript objects is that
if you access a missing member in Python, an exception is raised. In Javascript,
it returns `undefined`. Since we can't make any assumptions about whether the
Javascript member is missing or simply set to `undefined`, Python mirrors the
Javascript behavior. For example:

```javascript
// Javascript
class Point {
  constructor(x, y) {
    this.x = x;
    this.y = y;
  }
}
point = new Point(42, 43))
```

```python
# python
from js import point
assert point.y == 43
del point.y
assert point.y is None
```

### Python from Javascript

When passing a Python object to Javascript, the Javascript [Proxy
API](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy)
is used to delegate Javascript operations to the Python side. In general, the
Proxy API is more limited than what can be done with a Python extension, so
there are certain operations that are impossible or more cumbersome when using
Python from Javascript than vice versa. The most notable limitation is that
while Python has distinct ways of accessing attributes and items (`x.foo` and
`x[foo]`), Javascript conflates these two concepts. The following operations are
currently supported:

| Javascript     | Python                   |
|----------------|--------------------------|
| `foo in x`     | `hasattr(x, 'foo')`      |
| `x.foo`        | `getattr(x, 'foo')`      |
| `x.foo = bar`  | `setattr(x, 'foo', bar)` |
| `delete x.foo` | `delattr(x, 'foo')`      |
| `x.ownKeys()`  | `dir(x)`                 |
| `x(...)`       | `x(...)`                 |
| `x.foo(...)`   | `x.foo(...)`             |

An additional limitation is that when passing a Python object to Javascript,
there is no way for Javascript to automatically garbage collect that object.
Therefore, custom Python objects must be manually destroyed when passed to Javascript, or
they will leak. To do this, call `.destroy()` on the object, after which Javascript will no longer have access to the object.

```javascript
var foo = pyodide.pyimport('foo');
foo.call_method();
foo.destroy();
foo.call_method(); // This will raise an exception, since the object has been
                   // destroyed
```

## Using Python objects from Javascript

A Python object (in global scope) can be brought over to Javascript using the
`pyodide.pyimport` function. It takes a string giving the name of the variable,
and returns the object, converted to Javascript (See [type
conversions](type_conversions.md)).

```javascript
var sys = pyodide.pyimport('sys');
```

## Using Javascript objects from Python

Javascript objects can be accessed from Python using the special `js` module.
This module looks up attributes of the global (`window`) namespace on the
Javascript side.

```python
import js
js.document.title = 'New window title'
```

### Performance considerations

Looking up and converting attributes of the `js` module happens dynamically. In
most cases, where the value is small or results in a proxy, this is not an
issue. However, if the value takes a long time to convert from Javascript to
Python, you may want to store it in a Python variable or use the `from js import
...` syntax.

For example, given this large Javascript variable:

```javascript
var x = new Array(1000).fill(0)
```

Use it from Python as follows:

```python
import js
x = js.x  # conversion happens once here
for i in range(len(x)):
    item = x[i]  # we don't pay the conversion price each time here
```

Or alternatively:

```python
from js import x  # conversion happens once here
for i in range(len(x)):
    item = x[i]  # we don't pay the conversion price each time here
```
