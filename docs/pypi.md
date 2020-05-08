# Installing packages from PyPI

Pyodide has experimental support for installing pure Python wheels from PyPI.

**IMPORTANT:** Since the packages hosted at `files.pythonhosted.org` don't
support CORS requests, we use a CORS proxy at `cors-anywhere.herokuapp.com` to
get package contents. This makes a man-in-the-middle attack on the package
contents possible. However, this threat is minimized by the fact that the
integrity of each package is checked using a hash obtained directly from
`pypi.org`. We hope to have this improved in the future, but for now, understand
the risks and don't use any sensitive data with the packages installed using
this method.

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

```
def do_work(*args):
    import snowballstemmer
    stemmer = snowballstemmer.stemmer('english')
    print(stemmer.stemWords('go goes going gone'.split()))

import micropip
micropip.install('snowballstemmer').then(do_work)
```

## Complete example

Adapting the setup from the section on ["using pyodide from
javascript"](./using_pyodide_from_javascript.html) a complete example would be,

```html
<html>
<head>
  <meta charset="utf-8">
</head>
<body>
  <script type="text/javascript" src="https://pyodide.cdn.iodide.io/pyodide.js"></script>
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
