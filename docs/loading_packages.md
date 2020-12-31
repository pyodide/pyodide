(loading_packages)=
# Loading packages

Only the Python standard library and [six](https://pypi.org/project/six/) are 
available after importing Pyodide.
To use other packages, you’ll need to load them using either:
 - {ref}`pyodide.loadPackage <js_api_pyodide_loadPackage>` for packages built
   with pyodide, or 
 - `micropip.install` for pure Python packages with wheels available on PyPi or
   from other URLs.

```{note}
`micropip` can also be used to load packages built in pyodide (in
which case it relies on {ref}`pyodide.loadPackage <js_api_pyodide_loadPackage>`).
```

Alternatively you can run Python code without manually pre-loading packages.
You can do this with {ref}`pyodide.runPythonAsync <js_api_pyodide_runPythonAsync>` 
which will automatically download all packages that the code snippet imports. 
It only supports packages included in Pyodide (not on PyPi) at present.

## Loading packages with pyodide.loadPackage

Packages can be loaded by name, for those included in the official pyodide
repository using e.g.,
```js
pyodide.loadPackage('numpy')
```
It is also possible to load packages from custom URLs,
```js
pyodide.loadPackage('https://foo/bar/numpy.js')
```
in which case the URL must end with `<package-name>.js`.

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

(micropip)=
## Micropip

### Installing packages from PyPI

Pyodide supports installing pure Python wheels from PyPI with `micropip`. You
can use the `then` method on the `Promise` that {func}`micropip.install`
returns to do work once the packages have finished loading:

```py
def do_work(*args):
    import snowballstemmer
    stemmer = snowballstemmer.stemmer('english')
    print(stemmer.stemWords('go goes going gone'.split()))

import micropip
micropip.install('snowballstemmer').then(do_work)
```

Micropip implements file integrity validation by checking the hash of the
downloaded wheel against pre-recorded hash digests from the PyPi JSON API.

(micropip-installing-from-arbitrary-urls)=

### Installing wheels from arbitrary URLs

Pure python wheels can also be installed from any URL with micropip,
```py
import micropip
micropip.install(
    'https://example.com/files/snowballstemmer-2.0.0-py2.py3-none-any.whl'
)
```
Micropip currently decides whether a file is a url based on whether it ends in ".whl" or not.
The wheel name in the URL must follow [PEP 427 naming
convention](https://www.python.org/dev/peps/pep-0427/#file-format), which will
be the case if the wheels is made using standard python tools (`pip wheel`,
`setup.py bdist_wheel`).

All required dependencies need also to be previously installed with `micropip`
or {ref}`pyodide.loadPackage <js_api_pyodide_loadPackage>`.

If the file is on a remote server, it must set Cross-Origin Resource Sharing (CORS) headers to
allow access. Otherwise, you can prepend a CORS proxy to the URL. Note however
that using third-party CORS proxies has security implications, particularly
since we are not able to check the file integrity, unlike with installs from
PyPi.


## Example

Adapting the setup from the section on {ref}`using_from_javascript`
a complete example would be,

```html
<html>
<head>
  <meta charset="utf-8">
</head>
<body>
  <script type="text/javascript">
      // set the pyodide files URL (packages.json, pyodide.asm.data etc)
      window.languagePluginUrl = 'https://cdn.jsdelivr.net/pyodide/v0.16.1/full/';
  </script>
  <script type="text/javascript" src="https://cdn.jsdelivr.net/pyodide/v0.16.1/full/pyodide.js"></script>
  <script type="text/javascript">
    pythonCode = `
      def do_work(*args):
          import snowballstemmer
          stemmer = snowballstemmer.stemmer('english')
          print(stemmer.stemWords('go goes going gone'.split()))

      import micropip
      micropip.install('snowballstemmer').then(do_work)
    `

    languagePluginLoader.then(() => {
      return pyodide.loadPackage(['micropip'])
    }).then(() => {
      pyodide.runPython(pythonCode);
    })
  </script>
</body>
</html>
```
