(type-translations)=
# Type translations
In order to communicate between Python and Javascript, we "translate" objects
between the two languages. Depending on the type of the object we either
translate the object by implicitly converting it or by proxying it. By converting
an object we mean producing a new object in the target language which is the
equivalent of the object from the source language, for example converting a
Python string to the equivalent a Javascript string. By "proxying" an object we
mean producing a special object in the target language that forwards requests to
the source language. When we proxy a Javascript object into Python, the result
is a `JsProxy` object. When we proxy a Python object into Javascript, the result
is a `PyProxy` object. A proxied object can be explicitly converted using the
explicit conversion methods `JsProxy.to_py` and `PyProxy.toJs`.

Python to Javascript translations occur:

- when returning the final expression from a {any}`pyodide.runPython` call,
- when using {any}`pyodide.pyimport`,
- when passing arguments to a Javascript function called from Python,
- when returning the results of a Python function called from Javascript,
- when indexing a `PyProxy`

Javascript to Python translations occur:

- when using the `from js import ...` syntax
- passing arguments to a Python function called from Javascript
- returning the result of a Javascript function called from Python
- when indexing a `JsProxy`

## Round trip conversions 
Translating an object from Python to Javascript and then back to
Python is guaranteed to give an object that is equal to the original object
(with the exception of `nan` because `nan != nan`). Furthermore, if the object
is proxied into javascript, then translation back unwraps the proxy, and the
result of the round trip conversion `is` the original object (in the sense that
they live at the same memory address).

Translating an object from Javascript to Python and then back to
Javascript gives an object that is `===` to the original object (with the
exception of `NaN` because `NaN !== NaN`, and of `null` which after a round trip
is converted to `undefined`). Furthermore, if the object is proxied into Python,
then translation back unwraps the proxy, and the result of the round trip
conversion is the original object (in the sense that they live at the same
memory address).

## Implicit conversions

We only implicitly convert immutable types. This is to ensure that a mutable
type in Python can be modified in Javascript and vice-versa. Python has
immutable types such as `tuple` and `bytes` that have no equivalent in
Javascript. In order to ensure that round trip translations yield an object of
the same type as the original object, we proxy `tuple` and `bytes` objects.
Proxying tuples also has the benefit of ensuring that implicit conversions take
a constant amount of time.

The following immutable types are implicitly converted between Javascript and
Python. 

### Python to Javascript

| Python          | Javascript          |
|-----------------|---------------------|
| `int`           | `Number`            |
| `float`         | `Number`            |
| `str`           | `String`            |
| `bool`          | `Boolean`           |
| `None`          | `undefined`         |

### Javascript to Python

| Javascript      | Python                          |
|-----------------|---------------------------------|
| `Number`        | `int` or `float` as appropriate |
| `String`        | `str`                           |
| `Boolean`       | `bool`                          |
| `undefined`     | `None`                          |
| `null`          | `None`                          |


## Proxying

Any of the types not listed above are shared between languages using proxies
that allow methods and some operations to be called on the object from the other
language.


### Proxying from Javascript into Python

When most Javascript objects are translated into Python a `JsProxy` is returned.
The following operations are currently supported on a `JsProxy`. (More should be
possible in the future -- work is ongoing to make this more complete):

| Python                    | Javascript             |
|---------------------------|------------------------|
| `str(proxy)`             | `x.toString()`         |
| `proxy.foo`               | `x.foo`                |
| `proxy.foo = bar`         | `x.foo = bar`          |
| `del proxy.foo`           | `delete x.foo`         |
| `hasattr(proxy, "foo")`   | `"foo" in x`           |
| `proxy(...)`              | `x(...)`               |
| `proxy.foo(...)`          | `x.foo(...)`           |
| `proxy.new(...)`          | `new X(...)`           |
| `len(proxy)`              | `x.length` or `x.size` |
| `foo in proxy`            | `x.has(foo)`           |
| `proxy[foo]`              | `x.get(foo)`           |
| `proxy[foo] = bar`        | `x.set(foo, bar)`      |
| `del proxy[foo]`          | `x.delete(foo)`        |
| `proxy1 == proxy2`        | `x === y`              |
| `proxy.typeof`            | `typeof x`             |
| `iter(proxy)`             | `x[Symbol.iterator]()` |
| `next(proxy)`             | `x.next()`             |
| `await proxy`             | `await x`              |
| `proxy.object_entries()`  | `Object.entries(x)`    |

Some other code snippets:
```python
for v in proxy:
    # do something
```
is equivalent to:
```javascript
for(let v of x){
    // do something
}
```
The `dir` method has been overloaded to return all keys on the prototype chain
of `x`, so `dir(x)` roughly translates to:
```javascript
function dir(x){
    let result = [];
    do {
        result.push(...Object.getOwnPropertyNames(x));
    } while (x = Object.getPrototypeOf(x));
    return result;
}
```

As a special case, Javascript `Array`, `HTMLCollection`, and `NodeList` are
container types, but instead of using `array.get(7)` to get the 7th element,
javascript uses `array["7"]`. For these cases, we translate:

| Python                    | Javascript             |
|---------------------------|------------------------|
| `proxy[idx]`              | `x.toString()`         |
| `proxy[idx] = val`        | `x.foo`                |
| `idx in proxy`            | `idx in array`         |
| `del proxy[idx]`          | `proxy.splice(idx)`    |


### Proxying from Python into Javascript

When most Python objects are translated to Javascript a `PyProxy` is produced.
Fewer operations can be overloaded in Javascript than in Python so some
operations are more cumbersome on a `PyProxy` than on a `JsProxy`. The following
operations are currently supported:

| Javascript                 | Python                   |
|----------------------------|--------------------------|
| `foo in proxy`             | `hasattr(x, 'foo')`      |
| `proxy.foo`                | `x.foo`                  |
| `proxy.foo = bar`          | `x.foo = bar`            |
| `delete proxy.foo`         | `del x.foo`              |
| `proxy.ownKeys()`          | `dir(x)`                 |
| `proxy(...)`               | `x(...)`                 |
| `proxy.foo(...)`           | `x.foo(...)`             |
| `proxy.length` or `x.size` | `len(x)`                 |
| `proxy.has(foo)`           | `foo in x`               |
| `proxy.get(foo)`           | `x[foo]`                 |
| `proxy.set(foo, bar)`      | `x[foo] = bar`           |
| `proxy.delete(foo)`        | `del x[foo]`             |
| `x.type`                   | `type(x)`                |
| `x[Symbol.iterator]()`     | `iter(x)`                |
| `x.next()`                 | `next(x)`                |
| `await x`                  | `await x`                |
| `Object.entries(x)`        |  `repr(x)`               |

An additional limitation is that when proxying a Python object into Javascript,
there is no way for Javascript to automatically garbage collect the Proxy.
Therefore, the `PyProxy` must be manually destroyed when passed to Javascript,
or the proxied Python object will leak. To do this, call `PyProxy.destroy()` on
the `PyProxy`, after which Javascript will no longer have access to the Python
object. If no references to the Python object exist in Python either, then the
Python garbage collector can eventually collect it.

```javascript
let foo = pyodide.pyimport('foo');
foo.call_method();
foo.destroy();
foo.call_method(); // This will raise an exception, since the object has been
                   // destroyed
```


## Buffers

### Converting Javascript Typed Arrays to Python

Javascript typed arrays (`Int8Array` and friends) are translated to Python
`memoryviews`. This happens with a single binary memory copy (since Python can't
directly access arrays if they are outside of the wasm heap), and the data type
is preserved. This makes it easy to correctly convert the array to a Numpy array
using `numpy.asarray`:

```javascript
let array = new Float32Array([1, 2, 3]);
```

```python
from js import array
import numpy as np
numpy_array = np.asarray(array)
```

### Converting Python Buffer objects to Javascript

Python `bytes` and `buffer` objects are translated to Javascript as
`TypedArray`s without any memory copy at all. This conversion is thus very
efficient, but be aware that any changes to the buffer will be reflected in both
places.

Numpy arrays are currently converted to Javascript as nested (regular) Arrays. A
more efficient method will probably emerge as we decide on an ndarray
implementation for Javascript.


## Importing Python objects into Javascript

A Python object in the `__main__` global scope can imported into Javascript
using the {any}`pyodide.pyimport` function. Given the name of the Python object
to import, `pyimport` returns the object translated to Javascript.

```javascript
let sys = pyodide.pyimport('sys');
```
(type-translations_using-js-obj-from-py)=
## Importing Javascript objects into Python

Javascript objects in the
[`globalThis`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/globalThis)
global scope can be imported into Python using the `js` module.

When importing a name from the `js` module, the `js` module looks up Javascript
attributes of the `globalThis` scope and translates the Javascript objects into
Python. You can create your own custom javascript modules using
{any}`pyodide.registerJsModule`.

```python
import js
js.document.title = 'New window title'
from js.document.location import reload as reload_page
reload_page()
```
