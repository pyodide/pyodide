(type-translations)=

# Type translations

In order to communicate between Python and Javascript, we "translate" objects
between the two languages. Depending on the type of the object we either
translate the object by implicitly converting it or by proxying it. By
"converting" an object we mean producing a new object in the target language
which is the equivalent of the object from the source language, for example
converting a Python string to the equivalent a Javascript string. By "proxying"
an object we mean producing a special object in the target language that
forwards requests to the source language. When we proxy a Javascript object into
Python, the result is a {any}`JsProxy` object. When we proxy a Python object into
Javascript, the result is a {any}`PyProxy` object. A proxied object can be explicitly
converted using the explicit conversion methods {any}`JsProxy.to_py` and
{any}`PyProxy.toJs`.

Python to Javascript translations occur:

- when returning the final expression from a {any}`pyodide.runPython` call,
- when [importing Python objects into Javascript](type-translations_using-py-obj-from-js)
- when passing arguments to a Javascript function called from Python,
- when returning the results of a Python function called from Javascript,
- when accessing an attribute of a {any}`PyProxy`

Javascript to Python translations occur:

- when [importing from the `js` module](type-translations_using-js-obj-from-py)
- when passing arguments to a Python function called from Javascript
- when returning the result of a Javascript function called from Python
- when accessing an attribute of a {any}`JsProxy`

```{admonition} Memory Leaks and Python to Javascript translations
:class: warning

Any time a Python to Javascript translation occurs, it may create a {any}`PyProxy`.
To avoid memory leaks, you must store the {any}`PyProxy` and {any}`destroy <PyProxy.destroy>` it when you are
done with it. See {ref}`avoiding-leaks` for more info.
```

## Round trip conversions

Translating an object from Python to Javascript and then back to
Python is guaranteed to give an object that is equal to the original object
(with the exception of `nan` because `nan != nan`). Furthermore, if the object
is proxied into Javascript, then translation back unwraps the proxy, and the
result of the round trip conversion `is` the original object (in the sense that
they live at the same memory address).

Translating an object from Javascript to Python and then back to Javascript
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
mutable Python objects can be modified from Javascript and vice-versa. Python
has immutable types such as `tuple` and `bytes` that have no equivalent in
Javascript. In order to ensure that round trip translations yield an object of
the same type as the original object, we proxy `tuple` and `bytes` objects.

(type-translations_py2js-table)=

### Python to Javascript

The following immutable types are implicitly converted from Javascript to
Python:

| Python  | Javascript             |
| ------- | ---------------------- |
| `int`   | `Number` or `BigInt`\* |
| `float` | `Number`               |
| `str`   | `String`               |
| `bool`  | `Boolean`              |
| `None`  | `undefined`            |

\* An `int` is converted to a `Number` if the `int` is between -2^{53} and 2^{53}
inclusive, otherwise it is converted to a `BigInt`. (If the browser does not
support `BigInt` then a `Number` will be used instead. In this case,
conversion of large integers from Python to Javascript is lossy.)

(type-translations_js2py-table)=

### Javascript to Python

The following immutable types are implicitly converted from Python to
Javascript:

| Javascript  | Python                            |
| ----------- | --------------------------------- |
| `Number`    | `int` or `float` as appropriate\* |
| `BigInt`    | `int`                             |
| `String`    | `str`                             |
| `Boolean`   | `bool`                            |
| `undefined` | `None`                            |
| `null`      | `None`                            |

\* A number is converted to an `int` if it is between -2^{53} and 2^{53}
inclusive and its fractional part is zero. Otherwise it is converted to a
float.

## Proxying

Any of the types not listed above are shared between languages using proxies
that allow methods and some operations to be called on the object from the other
language.

(type-translations_jsproxy-dunders)=

### Proxying from Javascript into Python

When most Javascript objects are translated into Python a {any}`JsProxy` is returned.
The following operations are currently supported on a {any}`JsProxy`:

| Python                             | Javascript                        |
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

Note that each of these operations is only supported if the proxied Javascript
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

As a special case, Javascript `Array`, `HTMLCollection`, and `NodeList` are
container types, but instead of using `array.get(7)` to get the 7th element,
Javascript uses `array[7]`. For these cases, we translate:

| Python             | Javascript          |
| ------------------ | ------------------- |
| `proxy[idx]`       | `array[idx]`        |
| `proxy[idx] = val` | `array[idx] = val`  |
| `idx in proxy`     | `idx in array`      |
| `del proxy[idx]`   | `array.splice(idx)` |

(type-translations-pyproxy)=

### Proxying from Python into Javascript

When most Python objects are translated to Javascript a {any}`PyProxy` is produced.

Fewer operations can be overloaded in Javascript than in Python so some
operations are more cumbersome on a {any}`PyProxy` than on a {any}`JsProxy`. The following
operations are supported:

| Javascript                          | Python              |
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
See {ref}`avoiding-leaks`.
```javascript
let foo = pyodide.globals.get('foo');
foo();
foo.destroy();
foo(); // throws Error: Object has already been destroyed
```
````

## Explicit Conversion of Proxies

(type-translations-pyproxy-to-js)=

### Python to Javascript

Explicit conversion of a {any}`PyProxy` into a native Javascript object is done
with the {any}`PyProxy.toJs` method. You can also perform such a conversion in
Python using {any}`to_js <pyodide.to_js>` which behaves in much the same way. By
default, the `toJs` method does a recursive "deep" conversion, to do a shallow
conversion use `proxy.toJs({depth : 1})`. In addition to [the normal type
conversion](type-translations_py2js-table), `toJs` method performs the following
explicit conversions:

| Python          | Javascript   |
| --------------- | ------------ |
| `list`, `tuple` | `Array`      |
| `dict`          | `Map`        |
| `set`           | `Set`        |
| a buffer\*      | `TypedArray` |

\* Examples of buffers include bytes objects and numpy arrays.

If you need to convert `dict` instead to `Object`, you can pass
`Object.fromEntries` as the `dict_converter` argument:
`proxy.toJs({dict_converter : Object.fromEntries})`.

In Javascript, `Map` and `Set` keys are compared using object identity unless
the key is an immutable type (meaning a string, a number, a bigint, a boolean,
`undefined`, or `null`). On the other hand, in Python, `dict` and `set` keys are
compared using deep equality. If a key is encountered in a `dict` or `set` that
would have different semantics in Javascript than in Python, then a
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
    px.destory();
}
proxy.destroy();
```
As an alternative, if you wish to assert that the object should be fully
converted and no proxies should be created, you can use
`proxy.toJs({create_proxies : false})`. If a proxy would be created, an error is
raised instead.
````

(type-translations-jsproxy-to-py)=

### Javascript to Python

Explicit conversion of a {any}`JsProxy` into a native Python object is done with the
{any}`JsProxy.to_py` method. By default, the `to_py` method does a recursive "deep"
conversion, to do a shallow conversion use `proxy.to_py(depth=1)` The `to_py` method
performs the following explicit conversions:

| Javascript | Python |
| ---------- | ------ |
| `Array`    | `list` |
| `Object`\* | `dict` |
| `Map`      | `dict` |
| `Set`      | `set`  |

\* `to_py` will only convert an object into a dictionary if its constructor
is `Object`, otherwise the object will be left alone. Example:

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

In Javascript, `Map` and `Set` keys are compared using object identity unless
the key is an immutable type (meaning a string, a number, a bigint, a boolean,
`undefined`, or `null`). On the other hand, in Python, `dict` and `set` keys are
compared using deep equality. If a key is encountered in a `Map` or `Set` that
would have different semantics in Python than in Javascript, then a
`ConversionError` will be thrown. Also, in Javascript, `true !== 1` and `false !== 0`, but in Python, `True == 1` and `False == 0`. This has the result that a
Javascript map can use `true` and `1` as distinct keys but a Python `dict`
cannot. If the Javascript map contains both `true` and `1` a `ConversionError`
will be thrown.

## Buffers

### Using Javascript Typed Arrays from Python

Javascript ArrayBuffers and ArrayBuffer views (`Int8Array` and friends) are
proxied into Python. Python can't directly access arrays if they are outside of
the wasm heap so it's impossible to directly use these proxied buffers as Python
buffers. You can convert such a proxy to a Python `memoryview` using the `to_py`
api.
This makes it easy to correctly convert the array to a Numpy array
using `numpy.asarray`:

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
assign a Javascript buffer from / to a Python buffer which is appropriately
sized and contiguous. The assignment methods will only work if the data types
match, the total length of the buffers match, and the Python buffer is
contiguous.

These APIs are currently experimental, hopefully we will improve them in the
future.

(buffer_tojs)=

### Using Python Buffer objects from Javascript

Python objects supporting the [Python Buffer
protocol](https://docs.python.org/3/c-api/buffer.html) are proxied into
Javascript. The data inside the buffer can be accessed via the {any}`PyProxy.toJs` method or
the {any}`PyProxy.getBuffer` method. The `toJs` API copies the buffer into Javascript,
whereas the `getBuffer` method allows low level access to the WASM memory
backing the buffer. The `getBuffer` API is more powerful but requires care to
use correctly. For simple use cases the `toJs` API should be prefered.

If the buffer is zero or one-dimensional, then `toJs` will in most cases convert
it to a single `TypedArray`. However, in the case that the format of the buffer
is `'s'`, we will convert the buffer to a string and if the format is `'?'` we will
convert it to an Array of booleans.

If the dimension is greater than one, we will convert it to a nested Javascript
array, with the innermost dimension handled in the same way we would handle a 1d array.

An example of a case where you would not want to use the `toJs` method is when
the buffer is bitmapped image data. If for instance you have a 3d buffer shaped
1920 x 1080 x 4, then `toJs` will be extremely slow. In this case you could use
{any}`PyProxy.getBuffer`. On the other hand, if you have a 3d buffer shaped 1920
x 4 x 1080, the performance of `toJs` will most likely be satisfactory.
Typically the innermost dimension won't matter for performance.

The {any}`PyProxy.getBuffer` method can be used to retrieve a reference to a
Javascript typed array that points to the data backing the Python object,
combined with other metadata about the buffer format. The metadata is suitable
for use with a Javascript ndarray library if one is present. For instance, if
you load the Javascript [ndarray](https://github.com/scijs/ndarray) package, you
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

## Importing Objects

It is possible to access objects in one languge from the global scope in the
other language. It is also possible to create custom namespaces and access
objects on the custom namespaces.

(type-translations_using-py-obj-from-js)=

### Importing Python objects into Javascript

A Python object in the `__main__` global scope can imported into Javascript
using the {any}`pyodide.globals.get <PyProxy.get>` method. Given the name of the
Python object to import, it returns the object translated to Javascript.

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

### Importing Javascript objects into Python

Javascript objects in the
[`globalThis`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/globalThis)
global scope can be imported into Python using the `js` module.

When importing a name from the `js` module, the `js` module looks up Javascript
attributes of the `globalThis` scope and translates the Javascript objects into
Python.

```py
import js
js.document.title = 'New window title'
from js.document.location import reload as reload_page
reload_page()
```

You can also assign to Javascript global variables in this way:

```pyodide
pyodide.runPython("js.x = 2");
console.log(window.x); // 2
```

You can create your own custom Javascript modules using
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

(type-translations-errors)=

## Translating Errors

All entrypoints and exit points from Python code are wrapped in Javascript `try`
blocks. At the boundary between Python and Javascript, errors are caught,
converted between languages, and rethrown.

Javascript errors are wrapped in a {any}`JsException <pyodide.JsException>`.
Python exceptions are converted to a {any}`PythonError <pyodide.PythonError>`.
At present if an exception crosses between Python and Javascript several times,
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
careful to {any}`destroy() <PyProxy.destroy>` it when you are done with it or
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

(type-translations-proxy-arguments)=

## PyProxy memory management calling Javascript functions from Python

When you call a Javascript function from Python, any PyProxy arguments are
considered to be "borrowed" from the calling Python scope. After the function
call is done, they will be destroyed and will stop being accessible. An
exception is made if the Javascript function returns a Promise -- in this case,
the proxy arguments will only be destroyed when the Promise resolves.

This behavior is a bit complex, but it makes common uses convenient and turns
many memory leaks into explicit (though unfortunately somewhat confusing) error
messages.

As long as the function doesn't persist the arguments beyond the duration of the
function call, no memory is leaked and everything works as expected. For example,
no memory is leaked here:

```pyodide
function test(a){
    // We only use a during body of function, it gets destroyed afterwards.
    return a.get("x");
}
pyodide.runPython(`
    from js import test
    assert test({"x" : 3}) == 3
`);
```

If you persist the proxy, it will cause errors:

```pyodide
function test(a){
    window.a = a;
}
pyodide.runPython(`
    from js import test
    test({"x" : 3})
`);
a.get("x"); // Error: This borrowed proxy was automatically destroyed. [...]
```

If you want to persist the proxy, you need to use {any}`PyProxy.copy` or {any}`pyodide.create_proxy`.
Persisting the proxy from Javascript with {any}`PyProxy.copy`:

```pyodide
function test(a){
    window.a = a.copy();
}
pyodide.runPython(`
    from js import test
    test({"x" : 3})
`);
a.get("x"); // 3
```

Persisting the proxy from Python with {any}`pyodide.create_proxy`:

```pyodide
function test(a){
    window.a = a;
}
pyodide.runPython(`
    from js import test
    from pyodide import create_proxy
    test(create_proxy({"x" : 3}))
`);
a.get("x"); // 3
```

For example, {any}`pyodide.create_proxy` is useful for adding event listeners:

```py
from js import document
from pyodide import create_proxy
def f(*args):
    print("Clicked!")
f_proxy = create_proxy(f)
document.body.addEventListener("click", f_proxy)
# ... hold onto f_proxy,
# later we can remove it
document.body.removeEventListener("click", f_proxy)
f_proxy.destroy()
```

Asynchronous functions are a tricky case because they defer work to be done
later. We handle this by releasing the arguments in the `finally` handler of the
Promise. Of course this means if you return a promise that never resolves, it
will leak the arguments.

(avoiding-leaks)=

## Best practices for avoiding memory leaks

If the browser supports
[FinalizationRegistry](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/FinalizationRegistry)
then a `PyProxy` that is not part of a Javascript/Python reference cycle will
eventually be collected, but it is unpredictable when it will be collected. In
practice it typically takes a long time. Furthermore, the Javascript garbage
collector does not have any information about whether Python is experiencing
memory pressure. So it's best to aim to avoid leaks.

Here are some tips for how to do that when calling functions in one language from another.

There are four cases to consider here:

- calling a Python function from a Javascript function you wrote,
- calling a Python function from an existing Javascript callback,
- calling a Javascript function from Python code you wrote, or
- calling a Javascript function you wrote from an existing Python callback.

If you want to pass an existing Javascript function as a callback to an existing
Python function, you will need to define a wrapper around the Javascript
callback. That wrapper can then use approaches described here. Similarly with
the reverse direction.

### Calling Python functions from Javascript

In this case we just need to pay attention to the return value (and to the
function itself if you care about not leaking it).

```pyodide
pyodide.runPython("from itertools import accumulate");
let accumulate = pyodide.globals.get("accumulate");
let pyresult = accumulate([1,5,1,7]);
let result = [...pyresult];
pyresult.destroy();
accumulate.destroy();
console.log(result); // [1, 6, 7, 14]
```

### Calling Javascript functions from Python

When a Javascript function is called from Python, any PyProxy arguments are
considered to be "borrowed" from the local scope of the calling function. They
will be destroyed automatically after the function call is finished executing.
If the function is asynchronous (or generally if it returns a Promise), the
arguments will not be destroyed until the Promise resolves.

In many cases, the function will not persist the arguments after the function
call is complete, and this default behavior is perfect. However, some functions
are particularly meant to persist arguments, and then special care is needed.

For instance if you use `addEventListener` directly, it will not work:

```py
def callback():
    print("clicked!")
document.body.addEventListener("click", callback)
# From now on every time you click an exception is thrown =(
```

To do this correctly, use {any}`pyodide.create_proxy`:

```py
def callback():
    print("clicked!")
proxy = pyodide.create_proxy(callback)
from js import document
document.body.addEventListener("click", proxy)
# do other stuff, keep hold of proxy
document.body.removeEventListener("click", proxy)
proxy.destroy() # reclaim memory
```

If the argument is a function to be called once (for example, the argument to
`setTimeout`) you can use {any}`pyodide.create_once_callable`:

```py
from js import setTimeout
from pyodide import create_once_callable
def f():
    print("Calling f once without leaking it!")
setTimeout(create_once_callable(f), 500)
```

If you are using the promise methods {any}`PyProxy.then`, {any}`PyProxy.catch`,
or {any}`PyProxy.finally`, these have magic wrappers around them that
automatically do the equivalent of `create_once_callable` so you don't need to
do anything special to the arguments.

### Using a Javascript callback with an existing Python function

If you want to pass a Javascript callback to an existing Python function,
nothing needs to be done unless you wish to persist some of the arguments.

### Using a Python callback with an existing Javascript function

If it's only going to be called once:

```py
from pyodide import create_once_callable
from js import setTimeout
def my_callback():
    print("hi")
setTimeout(create_once_callable(my_callback), 1000)
```

If it's going to be called many times:

```py
from pyodide import create_proxy
from js import document
def my_callback():
    print("hi")
proxy = document.create_proxy(my_callback)
document.body.addEventListener("click", proxy)
# ...
# make sure to hold on to proxy
document.body.removeEventListener("click", proxy)
proxy.destroy()
```

Be careful with the return values. You might want to use {any}`to_js <pyodide.to_js>` on the result:

```py
from pyodide import to_js
def my_callback():
    result = [1, 2, 3]
    return to_js(result)
```
