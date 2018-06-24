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

Additionally, Python `bytes` and `buffer` objects are converted to/from Javascript
`Uint8ClampedArray` typed arrays.  In this case, however, the underlying data is
not copied, and is shared between the Python and Javascript sides.  This makes
passing raw memory between the languages (which in practice can be quite large)
very efficient.

Aside: This is the technology on which matplotlib images are passed to
Javascript to render in a canvas, and will be the basis of sharing Numpy arrays
with n-dimensional array data structures in Javascript.

## Class instances

Any of the types not listed above are shared between languages using proxies
that allow methods and some operators to be called on the object from the other
language.


When passing a Javascript object to Python, an extension type is used to
delegate Python operations to the Javascript side. The following operations are
currently supported. (More should be possible in the future -- work in ongoing
to make this more complete):

| Python         | Javascript     |
|----------------|----------------|
| `repr(x)`      | `x.toString()` |
| `x.foo`        | `x.foo`        |
| `x.foo = bar`  | `x.foo = bar`  |
| `x(...)`       | `x(...)`       |
| `x.foo(...)`   | `x.foo(...)`   |
| `X.new(...)`   | `new X(...)`   |
| `len(x)`       | `x.length`     |
| `x[foo]`       | `x[foo]`       |
| `x[foo] = bar` | `x[foo] = bar` |

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

Javascript objects can be accessed from Python using the `from js import ...`
syntax. The object must be in the global (`window`) namespace.

```python
from js import document
document.title = 'New window title'
```
