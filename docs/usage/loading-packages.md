(loading_packages)=

# Loading packages

Only the Python standard library is available after importing Pyodide.
To use other packages, you’ll need to load them using either:

- {py:func}`micropip.install` (Python) for pure Python packages with wheels as
  well as Pyodide packages (including Emscripten/wasm32 binary wheels). It can
  install packages from PyPI, the JsDelivr CDN or from other URLs.
- {js:func}`pyodide.loadPackage` (Javascript) for packages built with Pyodide.
  This is a function with less overhead but also more limited functionality.
  micropip uses this function to load Pyodide packages. In most cases you should
  be using micropip.

In some cases, and in particular in the REPL, packages are installed implicitly
from imports. The Pyodide REPL uses {js:func}`pyodide.loadPackagesFromImports`
to automatically download all packages that the code snippet imports. This is
useful since users might import unexpected packages in REPL. At present,
{js:func}`~pyodide.loadPackagesFromImports` will not download packages from
PyPI, it will only download packages included in the Pyodide distribution. See
{ref}`packages-in-pyodide` to check the full list of packages included in
Pyodide.

## How to chose between `micropip.install` and `pyodide.loadPackage`?

While {py:func}`micropip.install` is written in Python and
{js:func}`pyodide.loadPackage` in Javascript this has no incidence on when to
use each of these functions. Indeed, you can easily switch languages using the
{ref}`type-translations` with,

- from Javascript,
  ```javascript
  let micropip = pyodide.pyimport(package_name);
  ```
- from Python,
  ```
  import pyodide_js
  await pyodide_js.loadPackage('package_name')
  ```

Instead, the general advice is to use {py:func}`micropip.install` for everything
except in the following cases where {js:func}`pyodide.loadPackage` might be more
appropriate,

- to load micropip itself,
- when you are optimizing for size, do not want to install the `micropip`
  package, and do not need to install packages from PyPI with dependency resolution.

## Micropip

### Installing packages

Pyodide supports installing following types of packages with {mod}`micropip`,

- pure Python wheels from PyPI with {mod}`micropip`.
- pure Python and binary wasm32/emscripten wheels (also informally known as
  "Pyodide packages" or "packages built by Pyodide") from the JsDelivr CDN and
  custom URLs.
  {func}`micropip.install` is an async Python function which returns a
  coroutine, so it need to be called with an `await` clause to run.

```pyodide
await pyodide.loadPackage("micropip");
const micropip = pyodide.pyimport("micropip");
await micropip.install('snowballstemmer');
pyodide.runPython(`
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

Micropip decides whether a file is a URL based on whether it ends in ".whl" or
not. The wheel name in the URL must follow [PEP 427 naming
convention](https://www.python.org/dev/peps/pep-0427/#file-format), which will
be the case if the wheels is made using standard Python tools (`pip wheel`,
`setup.py bdist_wheel`). Micropip will also install the dependencies of the
wheel. If dependency resolution is not desired, you may pass `deps=False`.

```{admonition} Cross-Origin Resource Sharing (CORS)
:class: info

If the file is on a remote server, the server must set
[Cross-Origin Resource Sharing (CORS) headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
to allow access. If the server doesn't set CORS headers, you can use a CORS proxy.
Note that using third-party CORS proxies has security implications,
particularly since we are not able to check the file integrity, unlike with
installs from PyPI. See [this stack overflow
answer](https://stackoverflow.com/questions/43871637/no-access-control-allow-origin-header-is-present-on-the-requested-resource-whe/43881141#43881141)
for more information about CORS.
```

## Example

```html
<html>
  <head>
    <meta charset="utf-8" />
  </head>
  <body>
    <script type="text/javascript" src="{{PYODIDE_CDN_URL}}pyodide.js"></script>
    <script type="text/javascript">
      async function main() {
        let pyodide = await loadPyodide();
        await pyodide.loadPackage("micropip");
        const micropip = pyodide.pyimport("micropip");
        await micropip.install("snowballstemmer");
        await pyodide.runPython(`
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

## Loading packages with {js:func}`pyodide.loadPackage`

Packages included in the official Pyodide repository can be loaded using
{js:func}`~pyodide.loadPackage`:

```js
await pyodide.loadPackage("numpy");
```

It is also possible to load packages from custom URLs:

```js
await pyodide.loadPackage(
  "https://foo/bar/numpy-1.22.3-cp310-cp310-emscripten_3_1_13_wasm32.whl",
);
```

The file name must be a valid wheel name.

When you request a package from the official repository, all of the package's
dependencies are also loaded. There is no dependency resolution when loading
packages from custom URLs. If you want dependency resolution for custom URLs,
use {mod}`micropip`.

In general, loading a package twice is not permitted. However, one can override
a dependency by loading a custom URL with the same package name before loading
the dependent package.

Multiple packages can also be loaded at the same time by passing a list to
{js:func}`~pyodide.loadPackage`.

```js
await pyodide.loadPackage(["cycler", "pytz"]);
```

{js:func}`~pyodide.loadPackage` returns a {js:class}`Promise` which resolves when all the
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

```{eval-rst}
.. toctree::
   :hidden:

   packages-in-pyodide.md
   sdl.md
```
