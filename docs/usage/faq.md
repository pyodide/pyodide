# Frequently Asked Questions

(load-external-files-in-pyodide)=

## How can I load external files in Pyodide?

If you are using Pyodide in the browser, you should download external files and
save them to the virtual file system. The recommended way to do this is to zip
the files and unpack them into the file system with
{any}`pyodide.unpackArchive`:

```pyodide
let zipResponse = await fetch("myfiles.zip");
let zipBinary = await zipResponse.arrayBuffer();
pyodide.unpackArchive(zipBinary, "zip");
```

You can also download the files from Python using {any}`pyodide.http.pyfetch`,
which is a convenient wrapper of JavaScript `fetch`:

```pyodide
await pyodide.runPythonAsync(`
  from pyodide.http import pyfetch
  response = await pyfetch("https://some_url/myfiles.zip")
  await response.unpack_archive()
`)
```

If you are working in Node.js, you can mount a native folder into the file
system as follows:

```pyodide
FS.mkdir("/local_directory");
FS.mount(NODEFS, { root: "some/local/filepath" }, "/local_directory");
```

Then you can access the mounted folder from Python via the `/local_directory`
mount.

```{admonition} Why can't I just use urllib or requests?
:class: warning

We currently can’t use such packages since sockets are not available in Pyodide.
See {ref}`http-client-limit` for more information.
```

## Why can't I load files from the local file system?

For security reasons JavaScript in the browser is not allowed to load local data files
(for example, `file:///path/to/local/file.data`).
You will run into Network Errors, due to the [Same Origin Policy](https://en.wikipedia.org/wiki/Same-origin_policy).
There is a
[File System API](https://wicg.github.io/file-system-access/) supported in Chrome
but not in Firefox or Safari. See {ref}`nativefs-api` for experimental local file system
support.

For development purposes, you can serve your files with a
[web server](https://developer.mozilla.org/en-US/docs/Learn/Common_questions/set_up_a_local_testing_server).

## How can I execute code in a custom namespace?

The second argument to {any}`pyodide.runPython` is an options object which may
include a `globals` element which is a namespace for code to read from and write
to. The provided namespace must be a Python dictionary.

```pyodide
let my_namespace = pyodide.globals.get("dict")();
pyodide.runPython(`x = 1 + 1`, { globals: my_namespace });
pyodide.runPython(`y = x ** x`, { globals: my_namespace });
my_namespace.get("y"); // ==> 4
```

You can also use this approach to inject variables from JavaScript into the
Python namespace, for example:

```pyodide
let my_namespace = pyodide.toPy({ x: 2, y: [1, 2, 3] });
pyodide.runPython(
  `
  assert x == y[1]
  z = x ** x
  `,
  { globals: my_namespace }
);
my_namespace.get("z"); // ==> 4
```

## How to detect that code is run with Pyodide?

**At run time**, you can check if Python is built with Emscripten (which is the
case for Pyodide) with,

```py
import sys

if sys.platform == 'emscripten':
    # running in Pyodide or other Emscripten based build
```

To detect that a code is running with Pyodide specifically, you can check
for the loaded `pyodide` module,

```py
import sys

if "pyodide" in sys.modules:
   # running in Pyodide
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

## How do I create custom Python packages from JavaScript?

Put a collection of functions into a JavaScript object and use {any}`pyodide.registerJsModule`:
JavaScript:

```javascript
let my_module = {
  f: function (x) {
    return x * x + 1;
  },
  g: function (x) {
    console.log(`Calling g on argument ${x}`);
    return x;
  },
  submodule: {
    h: function (x) {
      return x * x - 1;
    },
    c: 2,
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

## How can I use a Python function as an event handler?

Note that the most straight forward way of doing this will not work:

```py
from js import document
def f(*args):
    document.querySelector("h1").innerHTML += "(>.<)"

document.body.addEventListener('click', f)
```

Now every time you click, an error will be raised (see {ref}`call-js-from-py`).

To do this correctly use {func}`pyodide.create_proxy` as follows:

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

## How can I use fetch with optional arguments from Python?

The most obvious translation of the JavaScript code won't work:

```py
import json
resp = await js.fetch('/someurl', {
  "method": "POST",
  "body": json.dumps({ "some" : "json" }),
  "credentials": "same-origin",
  "headers": { "Content-Type": "application/json" }
})
```

The `fetch` API ignores the options that we attempted to provide. You can do
this correctly in one of two ways:

```py
import json
from pyodide.ffi import to_js
from js import Object
resp = await js.fetch('example.com/some_api',
  method= "POST",
  body= json.dumps({ "some" : "json" }),
  credentials= "same-origin",
  headers= Object.fromEntries(to_js({ "Content-Type": "application/json" })),
)
```

or:

```py
import json
from pyodide.ffi import to_js
from js import Object
resp = await js.fetch('example.com/some_api', to_js({
  "method": "POST",
  "body": json.dumps({ "some" : "json" }),
  "credentials": "same-origin",
  "headers": { "Content-Type": "application/json" }
}, dict_converter=Object.fromEntries)
```

## How can I control the behavior of stdin / stdout / stderr?

If you wish to override `stdin`, `stdout` or `stderr` for the entire Pyodide
runtime, you can pass options to {any}`loadPyodide <globalThis.loadPyodide>`: If
you say

```
loadPyodide({
  stdin: stdin_func, stdout: stdout_func, stderr: stderr_func
});
```

then every time a line is written to `stdout` (resp. `stderr`), `stdout_func`
(resp `stderr_func`) will be called on the line. Every time `stdin` is read,
`stdin_func` will be called with zero arguments. It is expected to return a
string which is interpreted as a line of text.

Temporary redirection works much the same as it does in native Python: you can
overwrite `sys.stdin`, `sys.stdout`, and `sys.stderr` respectively. If you want
to do it temporarily, it's recommended to use
[`contextlib.redirect_stdout`](https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stdout)
and
[`contextlib.redirect_stderr`](https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stderr).
There is no `contextlib.redirect_stdin` but it is easy to make your own as
follows:

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
Welcome to Python 3.10's help utility!
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

## Why can't Micropip find a "pure Python wheel" for a package?

When installing a Python package from PyPI, micropip will produce an error if
it cannot find a pure Python wheel. To determine if a package has a pure
Python wheel manually, you can open its PyPi page (for instance
https://pypi.org/project/snowballstemmer/) and go to the "Download files" tab.
If this tab doesn't contain a file `*py3-none-any.whl` then the pure Python
wheel is missing.

This can happen for two reasons,

1. either the package is pure Python (you can check language composition for a
   package on Github), and its maintainers didn't upload a wheel.
   In this case, you can report this issue to the package issue tracker. As a
   temporary solution, you can also [build the
   wheel](https://packaging.python.org/en/latest/tutorials/packaging-projects/#generating-distribution-archives)
   yourself, upload it to some temporary location and install it with micropip
   from the corresponding URL.
2. or the package has binary extensions (e.g. C, Fortran or Rust), in which
   case it needs to be packaged in Pyodide. Please open [an
   issue](https://github.com/pyodide/pyodide/issues) after checking that an
   issue for this package doesn't exist already. Then follow
   {ref}`new-packages`.

## How can I change the behavior of {any}`runPython <pyodide.runPython>` and {any}`runPythonAsync <pyodide.runPythonAsync>`?

You can directly call Python functions from JavaScript. For most purposes it
makes sense to make your own Python function as an entrypoint and call that
instead of redefining `runPython`. The definitions of {any}`runPython <pyodide.runPython>` and {any}`runPythonAsync <pyodide.runPythonAsync>` are very
simple:

```javascript
function runPython(code) {
  pyodide.pyodide_py.code.eval_code(code, pyodide.globals);
}
```

```javascript
async function runPythonAsync(code) {
  return await pyodide.pyodide_py.code.eval_code_async(code, pyodide.globals);
}
```

To make your own version of {any}`runPython <pyodide.runPython>` you could do:

```pyodide
const my_eval_code = pyodide.runPython(`
  from pyodide.code import eval_code
  def my_eval_code(code, ns):
    extra_info = None
    result = eval_code(code, ns)
    return ns["extra_info"], result
  my_eval_code
`)

function myRunPython(code){
  return my_eval_code(code, pyodide.globals);
}
```

Then `myRunPython("2+7")` returns `[None, 9]` and
`myRunPython("extra_info='hello' ; 2 + 2")` returns `['hello', 4]`.
If you want to change which packages {any}`pyodide.loadPackagesFromImports` loads, you can
monkey patch {any}`pyodide.code.find_imports` which takes `code` as an argument
and returns a list of packages imported.

## Why can't I import a file I just wrote to the file system?

For example:

```py
from pathlib import Path
Path("mymodule.py").write_text("""\
def hello():
  print("hello world!")
"""
)
from mymodule import hello # may raise "ModuleNotFoundError: No module named 'mymodule'"
hello()
```

If you see this error, call `importlib.invalidate_caches()` before importing the module:

```py
import importlib
from pathlib import Path
Path("mymodule.py").write_text("""\
def hello():
  print("hello world!")
"""
)
importlib.invalidate_caches() # Make sure Python notices the new .py file
from mymodule import hello
hello()
```

## Why changes made to IndexedDB don't persist?

Unlike other filesystems, IndexedDB (pyodide.FS.filesystem.IDBFS) is an asynchronous filesystem.
This is because browsers offer only asynchronous interfaces for IndexedDB.
So in order to persist changes, you have to call
[`pyodide.FS.syncfs()`](https://emscripten.org/docs/api_reference/Filesystem-API.html#FS.syncfs).
See [Emscripten File System API](https://emscripten.org/docs/api_reference/Filesystem-API.html#persistent-data)
for more details.
