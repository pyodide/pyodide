# Frequently Asked Questions

## How can I load external Python files in Pyodide?

The two possible solutions are,

- include these files in a Python package, build a pure Python wheel with
  `python setup.py bdist_wheel` and
  {ref}`load it with micropip <micropip-installing-from-arbitrary-urls>`.
- fetch the Python code as a string and evaluate it in Python,
  ```js
  pyodide.runPython(await (await fetch('https://some_url/...')).text());
  ```

In both cases, files need to be served with a web server and cannot be loaded from local file system.

## Why can't I load files from the local file system?

For security reasons Javascript in the browser is not allowed to load local data
files. You need to serve them with a web-browser. Recently there is a
[Native File System API](https://wicg.github.io/file-system-access/) supported in Chrome
but not in Firefox.
[There is a discussion about implementing it for Firefox here.](https://github.com/mozilla/standards-positions/issues/154)


## How can I change the behavior of {any}`runPython <pyodide.runPython>` and {any}`runPythonAsync <pyodide.runPythonAsync>`?
You can directly call Python functions from Javascript. For many purposes it
makes sense to make your own Python function as an entrypoint and call that
instead of using `runPython`. The definitions of {any}`runPython
<pyodide.runPython>` and {any}`runPythonAsync <pyodide.runPythonAsync>` are very
simple:
```javascript
function runPython(code){
  pyodide.pyodide_py.eval_code(code, pyodide.globals);
}
```

```javascript
async function runPythonAsync(code, messageCallback, errorCallback) {
  await pyodide.loadPackagesFromImports(code, messageCallback, errorCallback);
  let coroutine = pyodide.pyodide_py.eval_code_async(code, pyodide.globals);
  try {
    let result = await coroutine;
    return result;
  } finally {
    coroutine.destroy();
  }
};
```
To make your own version of {any}`runPython <pyodide.runPython>` you could do:
```pyodide
pyodide.runPython(`
  import pyodide
  def my_eval_code(code, ns):
    extra_info = None
    result = pyodide.eval_code(code, ns)
    return ns["extra_info"], result]
`)

function myRunPython(code){
  return pyodide.globals.get("my_eval_code")(code, pyodide.globals);
}
```

Then `pyodide.myRunPython("2+7")` returns `[None, 9]` and
`pyodide.myRunPython("extra_info='hello' ; 2 + 2")` returns `['hello', 4]`.
If you want to change which packages {any}`pyodide.loadPackagesFromImports` loads, you can
monkey patch {any}`pyodide.find_imports` which takes `code` as an argument
and returns a list of packages imported.

## How can I execute code in a custom namespace?

The second argument to {any}`pyodide.eval_code` is a global namespace to execute the code in.
The namespace is a Python dictionary.
```javascript
let my_namespace = pyodide.globals.dict();
pyodide.runPython(`x = 1 + 1`, my_namespace);
pyodide.runPython(`y = x ** x`, my_namespace);
my_namespace.y; // ==> 4
```

## How to detect that code is run with Pyodide?

**At run time**, you can detect that a code is running with Pyodide using,
```py
import sys

if "pyodide" in sys.modules:
   # running in Pyodide
```

More generally you can detect Python built with Emscripten (which includes
Pyodide) with,
```py
import platform

if platform.system() == 'Emscripten':
    # running in Pyodide or other Emscripten based build
```

This however will not work at build time (i.e. in a `setup.py`) due to the way
the Pyodide build system works. It first compiles packages with the host compiler
(e.g. gcc) and then re-runs the compilation commands with emsdk. So the `setup.py` is
never run inside the Pyodide environment.

To detect Pyodide, **at build time** use,
```python
import os

if "PYODIDE" in os.environ:
    # building for Pyodide
```
We used to use the environment variable `PYODIDE_BASE_URL` for this purpose,
but this usage is deprecated.


## How do I create custom Python packages from Javascript?

Put a collection of functions into a Javascript object and use {any}`pyodide.registerJsModule`:
Javascript:
```javascript
let my_module = {
  f : function(x){
    return x*x + 1;
  },
  g : function(x){
    console.log(`Calling g on argument ${x}`);
    return x;
  },
  submodule : {
    h : function(x) {
      return x*x - 1;
    },
    c  : 2,
  },
};
pyodide.registerJsModule("my_js_module", my_module);
```
You can import your package like a normal Python package:
```py
import my_js_module
from my_js_module.submodule import h, c
assert my_js_module.f(7) == 50
assert h(9) == 80
assert c == 2
```
## How can I send a Python object from my server to Pyodide?

The best way to do this is with pickle. If the version of Python used in the
server exactly matches the version of Python used in the client, then objects
that can be successfully pickled can be sent to the client and unpickled in
Pyodide. If the versions of Python are different then for instance sending AST
is unlikely to work since there are breaking changes to Python AST in most
Python minor versions.

Similarly when pickling Python objects defined in a Python package, the package
version needs to match exactly between the server and pyodide.

Generally, pickles are portable between architectures (here amd64 and wasm32).
The rare cases when they are not portable, for instance currently tree based
models in scikit-learn, can be considered as a bug in the upstream library.

```{admonition} Security Issues with pickle
:class: warning

Unpickling data is similar to `eval`. On any public-facing server it is a really
bad idea to unpickle any data sent from the client. For sending data from client
to server, try some other serialization format like JSON.
```

## How can I use a Python function as an event handler and then remove it later?

Note that the most straight forward way of doing this will not work:
```py
from js import document
def f(*args):
    document.querySelector("h1").innerHTML += "(>.<)"

document.body.addEventListener('click', f)
document.body.removeEventListener('click', f)
```
This leaks `f` and does not remove the event listener (instead
`removeEventListener` will silently do nothing).

To do this correctly use :func:`pyodide.create_proxy` as follows:
```py
from js import document
from pyodide import create_proxy
def f(*args):
    document.querySelector("h1").innerHTML += "(>.<)"

proxy_f = create_proxy(f)
document.body.addEventListener('click', proxy_f)
# Store proxy_f in Python then later:
document.body.removeEventListener('click', proxy_f)
proxy_f.destroy()
```
This also avoids memory leaks.

## How can I use fetch with optional arguments from Python?
The most obvious translation of the Javascript code won't work:
```py
import json
resp = await js.fetch('/someurl', {
  "method": "POST",
  "body": json.dumps({ "some" : "json" }),
  "credentials": "same-origin",
  "headers": { "Content-Type": "application/json" }
})
```
this leaks the dictionary and the `fetch` api ignores the options that we
attempted to provide. You can do this correctly as follows:
```py
import json
from pyodide import to_js
from js import Object
resp = await js.fetch('example.com/some_api',
  method= "POST",
  body= json.dumps({ "some" : "json" }),
  credentials= "same-origin",
  headers= Object.fromEntries(to_js({ "Content-Type": "application/json" })),
)
```

## How can I control the behavior of stdin / stdout / stderr?
This works much the same as it does in native Python: you can overwrite
`sys.stdin`, `sys.stdout`, and `sys.stderr` respectively. If you want to do it
temporarily, it's recommended to use
[`contextlib.redirect_stdout`](https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stdout)
and
[`contextlib.redirect_stderr`](https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stderr).
There is no `contextlib.redirect_stdin` but it is easy to make your own as follows:
```py
from contextlib import _RedirectStream
class redirect_stdin(_RedirectStream):
    _stream = "stdin"
```
For example, if you do:
```
from io import StringIO
with redirect_stdin(StringIO("\n".join(["eval", "asyncio.ensure_future", "functools.reduce", "quit"]))):
  help()
```
it will print:
```
Welcome to Python 3.9's help utility!
<...OMITTED LINES>
Help on built-in function eval in module builtins:
eval(source, globals=None, locals=None, /)
    Evaluate the given source in the context of globals and locals.
<...OMITTED LINES>
Help on function ensure_future in asyncio:
asyncio.ensure_future = ensure_future(coro_or_future, *, loop=None)
    Wrap a coroutine or an awaitable in a future.
<...OMITTED LINES>
Help on built-in function reduce in functools:
functools.reduce = reduce(...)
    reduce(function, sequence[, initial]) -> value
    Apply a function of two arguments cumulatively to the items of a sequence,
<...OMITTED LINES>
You are now leaving help and returning to the Python interpreter.
```
