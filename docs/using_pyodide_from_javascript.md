# Using Pyodide from Javascript

This document describes using Pyodide directly from Javascript. For information about using Pyodide from Iodide, see [Using Pyodide from
Iodide](using_pyodide_from_iodide.md).

## Startup

To include Pyodide in your project you can use the following CDN URL,

  https://pyodide-cdn2.iodide.io/v0.15.0/full/pyodide.js

You can also download a release from
[Github releases](https://github.com/iodide-project/pyodide/releases)
(or build it yourself), include its contents in your distribution, and import
the `pyodide.js` file there from a `<script>` tag. See the following section on
[serving pyodide files](#serving-pyodide-files) for more details.

The `pyodide.js` file has a single `Promise` object which bootstraps the Python
environment: `languagePluginLoader`. Since this must happen asynchronously, it
is a `Promise`, which you must call `then` on to complete initialization. When
the promise resolves, pyodide will have installed a namespace in global scope:
`pyodide`.

```javascript
languagePluginLoader.then(() => {
  // pyodide is now ready to use...
  console.log(pyodide.runPython('import sys\nsys.version'));
});
```

## Running Python code

Python code is run using the `pyodide.runPython` function. It takes as input a
string of Python code. If the code ends in an expression, it returns the result
of the expression, converted to Javascript objects (See [type
conversions](type_conversions.md)).

```javascript
pyodide.runPython(`
import sys
sys.version
`);
```

## Complete example

Create and save a test `index.html` page with the following contents:
```html
<!DOCTYPE html>
<html>
  <head>
      <script type="text/javascript">
          // set the pyodide files URL (packages.json, pyodide.asm.data etc)
          window.languagePluginUrl = 'https://pyodide-cdn2.iodide.io/v0.15.0/full/';
      </script>
      <script src="https://pyodide-cdn2.iodide.io/v0.15.0/full/pyodide.js"></script>
  </head>
  <body>
    Pyodide test page <br>
    Open your browser console to see pyodide output
    <script type="text/javascript">
          languagePluginLoader.then(function () {
              console.log(pyodide.runPython(`
                  import sys
                  sys.version
              `));
              console.log(pyodide.runPython('print(1 + 2)'));
          });
    </script>
  </body>
</html>
```

## Loading packages

Only the Python standard library and `six` are available after importing
Pyodide. To use other libraries, you'll need to load their package using
`pyodide.loadPackage`. This downloads the file data over the network (as a
`.data` and `.js` index file) and installs the files in the virtual filesystem.

Packages can be loaded by name, for those included in the official pyodide
repository (e.g. `pyodide.loadPackage('numpy')`). It is also possible to load
packages from custom URLs (e.g.
`pyodide.loadPackage('https://foo/bar/numpy.js')`), in which case the URL must
end with `<package-name>.js`.

When you request a package from the official repository, all of that package's
dependencies are also loaded. Dependency resolution is not yet implemented
when loading packages from custom URLs.

Multiple packages can also be loaded in a single call,
```js
pyodide.loadPackage(['cycler', 'pytz'])
```

`pyodide.loadPackage` returns a `Promise`.

```javascript
pyodide.loadPackage('matplotlib').then(() => {
  // matplotlib is now available
});
```

## Alternative way to load packages and run Python code

Alternatively you can run Python code without manually pre-loading packages. You can do this with [pyodide.runPythonAsync](api_reference.md#pyodide-runpythonasync-code-messagecallback-errorcallback) function, which will automatically download all packages that the code snippet imports.

Note: although the function is called Async, it still blocks the main thread. To run Python code asynchronously see [WebWorker](using_pyodide_from_webworker.md)

## Alternative Example

```html
<!DOCTYPE html>
<head>
    <script type="text/javascript">
        window.languagePluginUrl = 'https://pyodide-cdn2.iodide.io/v0.15.0/full/';
    </script>
    <script src="https://pyodide-cdn2.iodide.io/v0.15.0/full/pyodide.js"></script>
</head>

<body>
  <p>You can execute any Python code. Just enter something in the box below and click the button.</p>
  <input id='code' value='sum([1,2,3,4,5])'>
  <button onclick='evaluatePython()'>Run</button>
  <br>
  <br>
  <div>
    Output:
  </div>
  <textarea id='output' style='width: 100%;' rows='6' disabled></textarea>

  <script>
    const output = document.getElementById("output")
    const code = document.getElementById("code")

    function addToOutput(s) {
      output.value+= `>>>${code.value}\n${s}\n`
    }

    output.value = 'Initializing...\n'
    // init pyodide
    languagePluginLoader.then(() => { output.value+='Ready!\n' })

    function evaluatePython() {
      pyodide.runPythonAsync(code.value)
        .then(output => addToOutput(output))
        .catch((err) => { addToOutput(err) })
    }
  </script>
</body>

</html>
```

## Accessing Python scope from JavaScript

You can also access from JavaScript all functions and variables defined in Python using the [pyodide.globals](api_reference.html#pyodide-globals) object.

For example, if you initialize the variable `x = numpy.ones([3,3])` in Python, you can access it from JavaScript in your browser's developer console as follows: `pyodide.globals.x`. he same goes for functions and imports.

You can try it yourself in the browser console:
```js
pyodide.globals.x
// >>> [Float64Array(3), Float64Array(3), Float64Array(3)]

// create the same 3x3 ndarray from js
let x = pyodide.globals.numpy.ones(new Int32Array([3, 3]))
// x >>> [Float64Array(3), Float64Array(3), Float64Array(3)]
```

## Serving pyodide files

If you built your pyodide distribution or downloaded the release tarball
you need to serve pyodide files with a appropriate headers.

Because browsers require WebAssembly files to have mimetype of
`application/wasm` we're unable to serve our files using Python's built-in
`SimpleHTTPServer` module.

Let's wrap Python's Simple HTTP Server and provide the appropiate mimetype for
WebAssembly files into a `pyodide_server.py` file (in the `pyodide_local`
directory):
```python
import sys
import socketserver
from http.server import SimpleHTTPRequestHandler


class Handler(SimpleHTTPRequestHandler):

    def end_headers(self):
        # Enable Cross-Origin Resource Sharing (CORS)
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


if sys.version_info < (3, 7, 5):
    # Fix for WASM MIME type for older Python versions
    Handler.extensions_map['.wasm'] = 'application/wasm'


if __name__ == '__main__':
    port = 8000
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print("Serving at: http://127.0.0.1:{}".format(port))
        httpd.serve_forever()
```

Let's test it out.
In your favourite shell, let's start our WebAssembly aware web server:
```bash
python pyodide_server.py
```

Point your WebAssembly aware browser to
[http://localhost:8000/index.html](http://localhost:8000/index.html) and open
your browser console to see the output from python via pyodide!
