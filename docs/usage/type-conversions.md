(type-translations)=

# Type translations

In order to communicate between Python and JavaScript, we "translate" objects
between the two languages. Depending on the type of the object we either
translate the object by implicitly converting it or by proxying it. By
"converting" an object we mean producing a new object in the target language
which is the equivalent of the object from the source language, for example
converting a Python string to the equivalent a JavaScript string. By "proxying"
an object we mean producing a special object in the target language that
forwards requests to the source language. When we proxy a JavaScript object into
Python, the result is a {any}`JsProxy` object. When we proxy a Python object
into JavaScript, the result is a {any}`PyProxy` object. A proxied object can be
explicitly converted using the explicit conversion methods {any}`JsProxy.to_py`
and {any}`PyProxy.toJs`.

Python to JavaScript translations occur:

- when returning the final expression from a {any}`pyodide.runPython` call,
- when [importing Python objects into JavaScript](type-translations_using-py-obj-from-js)
- when passing arguments to a JavaScript function called from Python,
- when returning the results of a Python function called from JavaScript,
- when accessing an attribute of a {any}`PyProxy`

JavaScript to Python translations occur:

- when [importing from the `js` module](type-translations_using-js-obj-from-py)
- when passing arguments to a Python function called from JavaScript
- when returning the result of a JavaScript function called from Python
- when accessing an attribute of a {any}`JsProxy`

```{admonition} Memory Leaks and Python to JavaScript translations
:class: warning

Any time a Python to JavaScript translation occurs, it may create a
{any}`PyProxy`. To avoid memory leaks, you must store the {any}`PyProxy` and
{any}`destroy <PyProxy.destroy>` it when you are done with it. See
{ref}`call-py-from-js` for more info.
```

## Round trip conversions

Translating an object from Python to JavaScript and then back to Python is
guaranteed to give an object that is equal to the original object. Furthermore,
if the object is proxied into JavaScript, then translation back unwraps the
proxy, and the result of the round trip conversion `is` the original object (in
the sense that they live at the same memory address). There are a few
exceptions:

1. `nan` is converted to `nan` after a round trip but `nan != nan`
2. proxies created using {any}`pyodide.create_proxy` will be unwrapped.

Translating an object from JavaScript to Python and then back to JavaScript
gives an object that is `===` to the original object. Furthermore, if the object
is proxied into Python, then translation back unwraps the proxy, and the result
of the round trip conversion is the original object (in the sense that they live
at the same memory address). There are a few exceptions:

1. `NaN` is converted to `NaN` after a round trip but `NaN !== NaN`,
2. `null` is converted to `undefined` after a round trip, and
3. a `BigInt` will be converted to a `Number` after a round trip unless its
   absolute value is greater than `Number.MAX_SAFE_INTEGER` (i.e., 2^53).

## Implicit conversions

We implicitly convert immutable types but not mutable types. This ensures that
mutable Python objects can be modified from JavaScript and vice-versa. Python
has immutable types such as `tuple` and `bytes` that have no equivalent in
JavaScript. In order to ensure that round trip translations yield an object of
the same type as the original object, we proxy `tuple` and `bytes` objects.

(type-translations_py2js-table)=

### Python to JavaScript

The following immutable types are implicitly converted from Python to
JavaScript:

| Python  | JavaScript             |
| ------- | ---------------------- |
| `int`   | `Number` or `BigInt`\* |
| `float` | `Number`               |
| `str`   | `String`               |
| `bool`  | `Boolean`              |
| `None`  | `undefined`            |

\* An `int` is converted to a `Number` if the `int` is between -2^53 and
2^53 inclusive, otherwise it is converted to a `BigInt`. (If the browser does
not support `BigInt` then a `Number` will be used instead. In this case,
conversion of large integers from Python to JavaScript is lossy.)

(type-translations_js2py-table)=

### JavaScript to Python

The following immutable types are implicitly converted from JavaScript to
Python:

| JavaScript  | Python                            |
| ----------- | --------------------------------- |
| `Number`    | `int` or `float` as appropriate\* |
| `BigInt`    | `int`                             |
| `String`    | `str`                             |
| `Boolean`   | `bool`                            |
| `undefined` | `None`                            |
| `null`      | `None`                            |

\* A number is converted to an `int` if it is between -2^53 and 2^53
inclusive and its fractional part is zero. Otherwise, it is converted to a
float.

## Proxying

Any of the types not listed above are shared between languages using proxies
that allow methods and some operations to be called on the object from the other
language.

(type-translations-jsproxy)=

### Proxying from JavaScript into Python

When most JavaScript objects are translated into Python a {any}`JsProxy` is
returned. The following operations are currently supported on a {any}`JsProxy`:

| Python                             | JavaScript                        |
| ---------------------------------- | --------------------------------- |
| `str(proxy)`                       | `x.toString()`                    |
| `proxy.foo`                        | `x.foo`                           |
| `proxy.foo = bar`                  | `x.foo = bar`                     |
| `del proxy.foo`                    | `delete x.foo`                    |
| `hasattr(proxy, "foo")`            | `"foo" in x`                      |
| `proxy(...)`                       | `x(...)`                          |
| `proxy.foo(...)`                   | `x.foo(...)`                      |
| {any}`proxy.new(...)<JsProxy.new>` | `new X(...)`                      |
| `len(proxy)`                       | `x.length` or `x.size`            |
| `foo in proxy`                     | `x.has(foo)` or `x.includes(foo)` |
| `proxy[foo]`                       | `x.get(foo)`                      |
| `proxy[foo] = bar`                 | `x.set(foo, bar)`                 |
| `del proxy[foo]`                   | `x.delete(foo)`                   |
| `proxy1 == proxy2`                 | `x === y`                         |
| `proxy.typeof`                     | `typeof x`                        |
| `iter(proxy)`                      | `x[Symbol.iterator]()`            |
| `next(proxy)`                      | `x.next()`                        |
| `await proxy`                      | `await x`                         |

Note that each of these operations is only supported if the proxied JavaScript
object supports the corresponding operation. See {any}`the JsProxy API docs <JsProxy>` for the rest of the methods supported on {any}`JsProxy`. Some other
code snippets:

```py
for v in proxy:
    # do something
```

is equivalent to:

```js
for (let v of x) {
  // do something
}
```

The `dir` method has been overloaded to return all keys on the prototype chain
of `x`, so `dir(x)` roughly translates to:

```js
function dir(x) {
  let result = [];
  do {
    result.push(...Object.getOwnPropertyNames(x));
  } while ((x = Object.getPrototypeOf(x)));
  return result;
}
```

As a special case, JavaScript `Array`, `HTMLCollection`, and `NodeList` are
container types, but instead of using `array.get(7)` to get the 7th element,
JavaScript uses `array[7]`. For these cases, we translate:

| Python             | JavaScript          |
| ------------------ | ------------------- |
| `proxy[idx]`       | `array[idx]`        |
| `proxy[idx] = val` | `array[idx] = val`  |
| `idx in proxy`     | `idx in array`      |
| `del proxy[idx]`   | `array.splice(idx)` |

(type-translations-pyproxy)=

### Proxying from Python into JavaScript

When most Python objects are translated to JavaScript a {any}`PyProxy` is
produced.

Fewer operations can be overloaded in JavaScript than in Python, so some
operations are more cumbersome on a {any}`PyProxy` than on a {any}`JsProxy`. The
following operations are supported:

| JavaScript                          | Python              |
| ----------------------------------- | ------------------- |
| `foo in proxy`                      | `hasattr(x, 'foo')` |
| `proxy.foo`                         | `x.foo`             |
| `proxy.foo = bar`                   | `x.foo = bar`       |
| `delete proxy.foo`                  | `del x.foo`         |
| `Object.getOwnPropertyNames(proxy)` | `dir(x)`            |
| `proxy(...)`                        | `x(...)`            |
| `proxy.foo(...)`                    | `x.foo(...)`        |
| `proxy.length`                      | `len(x)`            |
| `proxy.has(foo)`                    | `foo in x`          |
| `proxy.get(foo)`                    | `x[foo]`            |
| `proxy.set(foo, bar)`               | `x[foo] = bar`      |
| `proxy.delete(foo)`                 | `del x[foo]`        |
| `proxy.type`                        | `type(x)`           |
| `proxy[Symbol.iterator]()`          | `iter(x)`           |
| `proxy.next()`                      | `next(x)`           |
| `await proxy`                       | `await x`           |

````{admonition} Memory Leaks and PyProxy
:class: warning

Make sure to destroy PyProxies when you are done with them to avoid memory leaks.

```javascript
let foo = pyodide.globals.get('foo');
foo();
foo.destroy();
foo(); // throws Error: Object has already been destroyed
```
````

## Explicit Conversion of Proxies

(type-translations-pyproxy-to-js)=

### Python to JavaScript

Explicit conversion of a {any}`PyProxy` into a native JavaScript object is done
with the {any}`PyProxy.toJs` method. You can also perform such a conversion in
Python using {any}`to_js <pyodide.to_js>` which behaves in much the same way. By
default, the `toJs` method does a recursive "deep" conversion, to do a shallow
conversion use `proxy.toJs({depth : 1})`. In addition to [the normal type
conversion](type-translations_py2js-table), `toJs` method performs the following
explicit conversions:

| Python          | JavaScript   |
| --------------- | ------------ |
| `list`, `tuple` | `Array`      |
| `dict`          | `Map`        |
| `set`           | `Set`        |
| a buffer\*      | `TypedArray` |

\* Examples of buffers include bytes objects and numpy arrays.

If you need to convert `dict` instead to `Object`, you can pass
`Object.fromEntries` as the `dict_converter` argument:
`proxy.toJs({dict_converter : Object.fromEntries})`.

In JavaScript, `Map` and `Set` keys are compared using object identity unless
the key is an immutable type (meaning a string, a number, a bigint, a boolean,
`undefined`, or `null`). On the other hand, in Python, `dict` and `set` keys are
compared using deep equality. If a key is encountered in a `dict` or `set` that
would have different semantics in JavaScript than in Python, then a
`ConversionError` will be thrown.

See {ref}`buffer_tojs` for the behavior of `toJs` on buffers.

````{admonition} Memory Leaks and toJs
:class: warning

The {any}`toJs <PyProxy.toJs>` method can create many proxies at arbitrary
depth. It is your responsibility to manually `destroy` these proxies if you wish
to avoid memory leaks. The `pyproxies` argument to `toJs` is designed to help
with this:
```js
let pyproxies = [];
proxy.toJs({pyproxies});
// Do stuff
// pyproxies contains the list of proxies created by `toJs`. We can destroy them
// when we are done with them
for(let px of pyproxies){
    px.destroy();
}
proxy.destroy();
```
As an alternative, if you wish to assert that the object should be fully
converted and no proxies should be created, you can use
`proxy.toJs({create_proxies : false})`. If a proxy would be created, an error is
raised instead.
````

(type-translations-jsproxy-to-py)=

### JavaScript to Python

Explicit conversion of a {any}`JsProxy` into a native Python object is done with
the {any}`JsProxy.to_py` method. By default, the `to_py` method does a recursive
"deep" conversion, to do a shallow conversion use `proxy.to_py(depth=1)` The
`to_py` method performs the following explicit conversions:

| JavaScript | Python |
| ---------- | ------ |
| `Array`    | `list` |
| `Object`\* | `dict` |
| `Map`      | `dict` |
| `Set`      | `set`  |

\* `to_py` will only convert an object into a dictionary if its constructor is
`Object`, otherwise the object will be left alone. Example:

```pyodide
class Test {};
window.x = { "a" : 7, "b" : 2};
window.y = { "a" : 7, "b" : 2};
Object.setPrototypeOf(y, Test.prototype);
pyodide.runPython(`
    from js import x, y
    # x is converted to a dictionary
    assert x.to_py() == { "a" : 7, "b" : 2}
    # y is not a "Plain Old JavaScript Object", it's an instance of type Test so it's not converted
    assert y.to_py() == y
`);
```

In JavaScript, `Map` and `Set` keys are compared using object identity unless
the key is an immutable type (meaning a string, a number, a bigint, a boolean,
`undefined`, or `null`). On the other hand, in Python, `dict` and `set` keys are
compared using deep equality. If a key is encountered in a `Map` or `Set` that
would have different semantics in Python than in JavaScript, then a
`ConversionError` will be thrown. Also, in JavaScript, `true !== 1` and `false !== 0`, but in Python, `True == 1` and `False == 0`. This has the result that a
JavaScript map can use `true` and `1` as distinct keys but a Python `dict`
cannot. If the JavaScript map contains both `true` and `1` a `ConversionError`
will be thrown.

## Functions

(call-py-from-js)=

### Calling Python objects from JavaScript

If a Python object is callable, the proxy will be callable too. The arguments
will be translated from JavaScript to Python as appropriate, and the return
value will be translated from JavaScript back to Python. If the return value is
a `PyProxy`, you must explicitly destroy it or else it will be leaked.

An example:

```pyodide
let test = pyodide.runPython(`
    def test(x):
        return [n*n for n in x]
    test
`);
let result_py = test([1,2,3,4]);
// result_py is a PyProxy of a list.
let result_js = result_py.toJs();
// result_js is the array [1, 4, 9, 16]
result_py.destroy();
```

If a function is intended to be used from JavaScript, you can use {any}`to_js <pyodide.to_js>` on the return value. This prevents the return value from
leaking without requiring the JavaScript code to explicitly destroy it. This is
particularly important for callbacks.

```pyodide
let test = pyodide.runPython(`
    from pyodide import to_js
    def test(x):
        return to_js([n*n for n in x])
    test
`);
let result = test([1,2,3,4]);
// result is the array [1, 4, 9, 16], nothing needs to be destroyed.
```

If you need to use a key word argument, use {any}`callKwargs <PyProxy.callKwargs>`. The last argument should be a JavaScript object with the
key value arguments.

```pyodide
let test = pyodide.runPython(`
    from pyodide import to_js
    def test(x, *, offset):
        return to_js([n*n + offset for n in x])
    to_js(test)
`);
let result = test.callKwargs([1,2,3,4], { offset : 7});
// result is the array [8, 12, 16, 23]
```

(call-js-from-py)=

### Calling JavaScript functions from Python

What happens when calling a JavaScript function from Python is a bit more
complicated than calling a Python function from JavaScript. If there are any
keyword arguments, they are combined into a JavaScript object and used as the
final argument. Thus, if you call:

```py
f(a=2, b=3)
```

then the JavaScript function receives one argument which is a JavaScript object
`{a : 2, b : 3}`.

When a JavaScript function is called, and it returns anything but a promise, if
the result is a `PyProxy` it is destroyed. Also, any arguments that are
PyProxies that were created in the process of argument conversion are also
destroyed. If the `PyProxy` was created in Python using
{any}`pyodide.create_proxy` it is not destroyed.

When a JavaScript function returns a `Promise` (for example, if the function is
an `async` function), it is assumed that the `Promise` is going to do some work
that uses the arguments of the function, so it is not safe to destroy them until
the `Promise` resolves. In this case, the proxied function returns a Python
`Future` instead of the original `Promise`. When the `Promise` resolves, the
result is converted to Python and the converted value is used to resolve the
`Future`. Then if the result is a `PyProxy` it is destroyed. Any PyProxies
created in converting the arguments are also destroyed at this point.

As a result of this, if a `PyProxy` is persisted to be used later, then it must
either be copied using {any}`PyProxy.copy` in JavaScript, or it must be created
with {any}`pyodide.create_proxy` or `pyodide.create_once_callable`. If it's only
going to be called once use `pyodide.create_once_callable`:

```py
from pyodide import create_once_callable
from js import setTimeout
def my_callback():
    print("hi")
setTimeout(create_once_callable(my_callback), 1000)
```

If it's going to be called many times use `create_proxy`:

```py
from pyodide import create_proxy
from js import document
def my_callback():
    print("hi")
proxy = pyodide.create_proxy(my_callback)
document.body.addEventListener("click", proxy)
# ...
# make sure to hold on to proxy
document.body.removeEventListener("click", proxy)
proxy.destroy()
```

## Buffers

### Using JavaScript Typed Arrays from Python

JavaScript ArrayBuffers and ArrayBuffer views (`Int8Array` and friends) are
proxied into Python. Python can't directly access arrays if they are outside
the WASM heap, so it's impossible to directly use these proxied buffers as Python
buffers. You can convert such a proxy to a Python `memoryview` using the `to_py`
api. This makes it easy to correctly convert the array to a Numpy array using
`numpy.asarray`:

```pyodide
self.jsarray = new Float32Array([1,2,3, 4, 5, 6]);
pyodide.runPython(`
    from js import jsarray
    array = jsarray.to_py()
    import numpy as np
    numpy_array = np.asarray(array).reshape((2,3))
    print(numpy_array)
`);
```

After manipulating `numpy_array` you can assign the value back to
`jsarray` using {any}`JsProxy.assign`:

```pyodide
pyodide.runPython(`
    numpy_array[1,1] = 77
    jsarray.assign(a)
`);
console.log(jsarray); // [1, 2, 3, 4, 77, 6]
```

The {any}`JsProxy.assign` and {any}`JsProxy.assign_to` methods can be used to
assign a JavaScript buffer from / to a Python buffer which is appropriately
sized and contiguous. The assignment methods will only work if the data types
match, the total length of the buffers match, and the Python buffer is
contiguous.

These APIs are currently experimental, hopefully we will improve them in the
future.

(buffer_tojs)=

### Using Python Buffer objects from JavaScript

Python objects supporting the [Python Buffer
protocol](https://docs.python.org/3/c-api/buffer.html) are proxied into
JavaScript. The data inside the buffer can be accessed via the
{any}`PyProxy.toJs` method or the {any}`PyProxy.getBuffer` method. The `toJs`
API copies the buffer into JavaScript, whereas the `getBuffer` method allows low
level access to the WASM memory backing the buffer. The `getBuffer` API is more
powerful but requires care to use correctly. For simple use cases the `toJs` API
should be preferred.

If the buffer is zero or one-dimensional, then `toJs` will in most cases convert
it to a single `TypedArray`. However, in the case that the format of the buffer
is `'s'`, we will convert the buffer to a string and if the format is `'?'` we
will convert it to an Array of booleans.

If the dimension is greater than one, we will convert it to a nested JavaScript
array, with the innermost dimension handled in the same way we would handle a 1d
array.

An example of a case where you would not want to use the `toJs` method is when
the buffer is bitmapped image data. If for instance you have a 3d buffer shaped
1920 x 1080 x 4, then `toJs` will be extremely slow. In this case you could use
{any}`PyProxy.getBuffer`. On the other hand, if you have a 3d buffer shaped 1920
x 4 x 1080, the performance of `toJs` will most likely be satisfactory.
Typically, the innermost dimension won't matter for performance.

The {any}`PyProxy.getBuffer` method can be used to retrieve a reference to a
JavaScript typed array that points to the data backing the Python object,
combined with other metadata about the buffer format. The metadata is suitable
for use with a JavaScript ndarray library if one is present. For instance, if
you load the JavaScript [ndarray](https://github.com/scijs/ndarray) package, you
can do:

```js
let proxy = pyodide.globals.get("some_numpy_ndarray");
let buffer = proxy.getBuffer();
proxy.destroy();
try {
  if (buffer.readonly) {
    // We can't stop you from changing a readonly buffer, but it can cause undefined behavior.
    throw new Error("Uh-oh, we were planning to change the buffer");
  }
  let array = new ndarray(
    buffer.data,
    buffer.shape,
    buffer.strides,
    buffer.offset
  );
  // manipulate array here
  // changes will be reflected in the Python ndarray!
} finally {
  buffer.release(); // Release the memory when we're done
}
```

(type-translations-errors)=

## Errors

All entrypoints and exit points from Python code are wrapped in JavaScript `try`
blocks. At the boundary between Python and JavaScript, errors are caught,
converted between languages, and rethrown.

JavaScript errors are wrapped in a {any}`JsException <pyodide.JsException>`.
Python exceptions are converted to a {any}`PythonError <pyodide.PythonError>`.
At present if an exception crosses between Python and JavaScript several times,
the resulting error message won't be as useful as one might hope.

In order to reduce memory leaks, the {any}`PythonError <pyodide.PythonError>`
has a formatted traceback, but no reference to the original Python exception.
The original exception has references to the stack frame and leaking it will
leak all the local variables from that stack frame. The actual Python exception
will be stored in
[`sys.last_value`](https://docs.python.org/3/library/sys.html#sys.last_value) so
if you need access to it (for instance to produce a traceback with certain
functions filtered out), use that.

```{admonition} Be careful Proxying Stack Frames
:class: warning
If you make a {any}`PyProxy` of ``sys.last_value``, you should be especially
careful to {any}`destroy() <PyProxy.destroy>` it when you are done with it, or
you may leak a large amount of memory if you don't.
```

The easiest way is to only handle the exception in Python:

```pyodide
pyodide.runPython(`
def reformat_exception():
    from traceback import format_exception
    # Format a modified exception here
    # this just prints it normally but you could for instance filter some frames
    return "".join(
        traceback.format_exception(sys.last_type, sys.last_value, sys.last_traceback)
    )
`);
let reformat_exception = pyodide.globals.get("reformat_exception");
try {
    pyodide.runPython(some_code);
} catch(e){
    // replace error message
    e.message = reformat_exception();
    throw e;
}
```

## Importing Objects

It is possible to access objects in one language from the global scope in the
other language. It is also possible to create custom namespaces and access
objects on the custom namespaces.

(type-translations_using-py-obj-from-js)=

### Importing Python objects into JavaScript

A Python object in the `__main__` global scope can be imported into JavaScript
using the {any}`pyodide.globals.get <PyProxy.get>` method. Given the name of the
Python object to import, it returns the object translated to JavaScript.

```js
let sys = pyodide.globals.get("sys");
```

As always, if the result is a `PyProxy` and you care about not leaking the
Python object, you must destroy it when you are done. It's also possible to set
values in the Python global scope with {any}`pyodide.globals.set <PyProxy.set>`
or remove them with {any}`pyodide.globals.delete <PyProxy.delete>`:

```pyodide
pyodide.globals.set("x", 2);
pyodide.runPython("print(x)"); // Prints 2
```

If you execute code with a custom globals dictionary, you can use a similar
approach:

```pyodide
let my_py_namespace = pyodide.globals.get("dict")();
pyodide.runPython("x=2", my_py_namespace);
let x = my_py_namespace.get("x");
```

(type-translations_using-js-obj-from-py)=

### Importing JavaScript objects into Python

JavaScript objects in the
[`globalThis`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/globalThis)
global scope can be imported into Python using the `js` module.

When importing a name from the `js` module, the `js` module looks up JavaScript
attributes of the `globalThis` scope and translates the JavaScript objects into
Python.

```py
import js
js.document.title = 'New window title'
from js.document.location import reload as reload_page
reload_page()
```

You can also assign to JavaScript global variables in this way:

```pyodide
pyodide.runPython("js.x = 2");
console.log(window.x); // 2
```

You can create your own custom JavaScript modules using
{any}`pyodide.registerJsModule` and they will behave like the `js` module except
with a custom scope:

```pyodide
let my_js_namespace = { x : 3 };
pyodide.registerJsModule("my_js_namespace", my_js_namespace);
pyodide.runPython(`
    from my_js_namespace import x
    print(x) # 3
    my_js_namespace.y = 7
`);
console.log(my_js_namespace.y); // 7
```
