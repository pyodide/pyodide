# Installing packages from PyPI

Pyodide has experimental support for installing pure Python wheels from PyPI.

For use in Iodide:

```
%% py
import micropip
micropip.install('snowballstemmer')

# Iodide implicitly waits for the promise to resolve when the packages have finished
# installing...

%% py
import snowballstemmer
stemmer = snowballstemmer.stemmer('english')
stemmer.stemWords('go goes going gone'.split())
```

For use outside of Iodide (just Python), you can use the `then` method on the
`Promise` that `micropip.install` returns to do work once the packages have
finished loading:

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

## Installing wheels from arbitrary URLs

Pure python wheels can also be installed from any URL with micropip,
```py
import micropip
micropip.install(
    'https://example.com/files/snowballstemmer-2.0.0-py2.py3-none-any.whl'
)
```

The wheel name in the URL must follow [PEP 427 naming
convention](https://www.python.org/dev/peps/pep-0427/#file-format), which will
be the case if the wheels is made using standard python tools (`pip wheel`,
`setup.py bdist_wheel`).

All required dependencies need also to be previously installed with `micropip`
or `pyodide.loadPackage`.

The remote server must set Cross-Origin Resource Sharing (CORS) headers to
allow access. Otherwise, you can prepend a CORS proxy to the URL. Note however
that using third-party CORS proxies has security implications, particularly
since we are not able to check the file integrity, unlike with installs from
PyPi.


## Complete example

Adapting the setup from the section on ["using pyodide from
javascript"](./using_pyodide_from_javascript.html) a complete example would be,

```html
<html>
<head>
  <meta charset="utf-8">
</head>
<body>
  <script type="text/javascript">
      // set the pyodide files URL (packages.json, pyodide.asm.data etc)
      window.languagePluginUrl = 'https://pyodide-cdn2.iodide.io/v0.15.0/full/';
  </script>
  <script type="text/javascript" src="https://pyodide-cdn2.iodide.io/v0.15.0/full/pyodide.js"></script>
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
