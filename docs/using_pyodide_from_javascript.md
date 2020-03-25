# Using Pyodide from Javascript

This document describes using Pyodide directly from Javascript. For information
about using Pyodide from Iodide, see [Using Pyodide from
Iodide](using_pyodide_from_iodide.md).

## Startup

Include `pyodide.js` in your project.

The recommended way to include Pyodide in your project is to download a release
from [here](https://github.com/iodide-project/pyodide/releases) and include the
contents in your distribution, and import the `pyodide.js` file there from a
`<script>` tag.

For prototyping purposes, you may also use the following CDN URL, though doing
so is not recommended, since it isn't versioned and could change or be unstable
at any time:

  https://pyodide.cdn.iodide.io/pyodide.js

This file has a single `Promise` object which bootstraps the Python environment:
`languagePluginLoader`. Since this must happen asynchronously, it is a
`Promise`, which you must call `then` on to complete initialization. When the
promise resolves, pyodide will have installed a namespace in global scope:
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
pyodide.runPython('import sys\nsys.version');
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

## Complete example

Grab the latest release tarball from the [releases
page](https://github.com/iodide-project/pyodide/releases/) and expand its
contents into a `pyodide_local` directory.

Create and save a test `index.html` page (in the `pyodide_local` directory)
with the following contents:
```html
<!DOCTYPE html>
<html>
<head>
    <script type="text/javascript">
        // set the pyodide files URL (packages.json, pyodide.asm.data etc)
        window.languagePluginUrl = 'http://localhost:8000/';
    </script>
    <script src="pyodide.js"></script>
</head>
<body>
  Pyodide test page <br>
  Open your browser console to see pyodide output
  <script type="text/javascript">
        languagePluginLoader.then(function () {
            console.log(pyodide.runPython('import sys\nsys.version'));
            console.log(pyodide.runPython('print(1 + 2)'));
        });
  </script>
</body>
```

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
