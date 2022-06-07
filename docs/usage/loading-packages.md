(loading_packages)=

# Loading packages

Only the Python standard library is available after importing Pyodide.
To use other packages, you’ll need to load them using either:

- {any}`pyodide.loadPackage` for packages built with Pyodide, or
- {any}`micropip.install` for pure Python packages with wheels available on PyPI or
  from other URLs.

```{note}
{mod}`micropip` can also be used to load packages built in Pyodide (in
which case it relies on {any}`pyodide.loadPackage`).
```

If you use {any}`pyodide.loadPackagesFromImports` Pyodide will automatically
download all packages that the code snippet imports. This is particularly useful
for making a repl since users might import unexpected packages. At present,
{any}`loadPackagesFromImports <pyodide.loadPackagesFromImports>` will not
download packages from PyPI, it will only download packages included in the
Pyodide distribution. See {ref}`packages-in-pyodide` to check the full list of packages included in Pyodide.

## Loading packages with {any}`pyodide.loadPackage`

Packages included in the official Pyodide repository can be loaded using
{any}`pyodide.loadPackage`:

```js
pyodide.loadPackage("numpy");
```

It is also possible to load packages from custom URLs:

```js
pyodide.loadPackage("https://foo/bar/numpy.js");
```

The file name in the URL must be `<package-name>.js` and there must be an
accompanying file called `<package-name>.data` in the same directory.

When you request a package from the official repository, all of that package's
dependencies are also loaded. Dependency resolution is not yet implemented when
loading packages from custom URLs.

In general, loading a package twice is not permitted. However, one can override
a dependency by loading a custom URL with the same package name before loading
the dependent package.

Multiple packages can also be loaded at the same time by passing a list to {any}`pyodide.loadPackage`.

```js
pyodide.loadPackage(["cycler", "pytz"]);
```

{any}`pyodide.loadPackage` returns a `Promise` which resolves when all the
packages are finished loading:

```javascript
let pyodide;
async function main() {
  pyodide = await loadPyodide();
  await pyodide.loadPackage("matplotlib");
  // matplotlib is now available
}
main();
```

(micropip)=

## Micropip

### Installing packages from PyPI

Pyodide supports installing pure Python wheels from PyPI with {mod}`micropip`.
{func}`micropip.install` returns a Python
[Future](https://docs.python.org/3/library/asyncio-future.html) so you can await
the future or otherwise use the Python future API to do work once the packages
have finished loading:

```pyodide
pyodide.runPythonAsync(`
  import micropip
  await micropip.install('snowballstemmer')
  import snowballstemmer
  stemmer = snowballstemmer.stemmer('english')
  print(stemmer.stemWords('go goes going gone'.split()))
`);
```

Micropip implements file integrity validation by checking the hash of the
downloaded wheel against pre-recorded hash digests from the PyPI JSON API.

(micropip-installing-from-arbitrary-urls)=

### Installing wheels from arbitrary URLs

Pure Python wheels can also be installed from any URL with {mod}`micropip`,

```py
import micropip
micropip.install(
    'https://example.com/files/snowballstemmer-2.0.0-py2.py3-none-any.whl'
)
```

Micropip decides whether a file is a URL based on whether it ends in ".whl" or not.
The wheel name in the URL must follow [PEP 427 naming
convention](https://www.python.org/dev/peps/pep-0427/#file-format), which will
be the case if the wheels is made using standard Python tools (`pip wheel`,
`setup.py bdist_wheel`).

All required dependencies must have been previously installed with {mod}`micropip`
or {any}`pyodide.loadPackage`.

```{admonition} Cross-Origin Resource Sharing (CORS)
:class: info

If the file is on a remote server, the server must set
[Cross-Origin Resource Sharing (CORS) headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
to allow access. Otherwise, you can prepend a CORS proxy to the
URL. Note however that using third-party CORS proxies has security implications,
particularly since we are not able to check the file integrity, unlike with
installs from PyPI.
```

## Example

```html
<html>
  <head>
    <meta charset="utf-8" />
  </head>
  <body>
    <script
      type="text/javascript"
      src="{{PYODIDE_CDN_URL}}/pyodide.js"
    ></script>
    <script type="text/javascript">
      async function main() {
        let pyodide = await loadPyodide();
        await pyodide.loadPackage("micropip");
        await pyodide.runPythonAsync(`
        import micropip
        await micropip.install('snowballstemmer')
        import snowballstemmer
        stemmer = snowballstemmer.stemmer('english')
        print(stemmer.stemWords('go goes going gone'.split()))
      `);
      }
      main();
    </script>
  </body>
</html>
```

```{eval-rst}
.. toctree::
   :hidden:

   packages-in-pyodide.md
```
