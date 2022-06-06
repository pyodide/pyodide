# Using Pyodide

Pyodide may be used in any context where you want to run Python inside a web
browser or a backend JavaScript environment.

## Web browsers

To use Pyodide on a web page you need to load `pyodide.js` and initialize
Pyodide with {any}`loadPyodide <globalThis.loadPyodide>` specifying an index URL for packages:

```html-pyodide
<!DOCTYPE html>
<html>
  <head>
      <script src="{{PYODIDE_CDN_URL}}pyodide.js"></script>
  </head>
  <body>
    <script type="text/javascript">
      async function main(){
        let pyodide = await loadPyodide();
        console.log(pyodide.runPython("1 + 2"));
      }
      main();
    </script>
  </body>
</html>
```

See the {ref}`quickstart` for a walk through tutorial as well as
{ref}`loading_packages` and {ref}`type-translations` for a more in depth
discussion about existing capabilities.

You can also use the [Pyodide NPM
package](https://www.npmjs.com/package/pyodide) to integrate Pyodide into your
application.

```{note}
To avoid confusion, note that:
 - `cdn.jsdelivr.net/pyodide/` distributes Python packages built with Pyodide as well as `pyodide.js`
 - `cdn.jsdelivr.net/npm/pyodide@0.19.0/` is a mirror of the Pyodide NPM package, which includes none of the WASM files
```

### Supported browsers

Pyodide works in any modern web browser with WebAssembly support.

**Tier 1** browsers are tested as part of the test suite with continuous integration,

| Browser | Minimal supported version | Release date    |
| ------- | ------------------------- | --------------- |
| Firefox | 70.0                      | 22 October 2019 |
| Chrome  | 71.0                      | 4 December 2018 |

Chrome 89 and 90 have bugs in the webassembly compiler which makes using Pyodide
with them unstable. Known problems occur in numpy and have been observed
occasionally in other packages. See {issue}`1384`.

```{note}
Latest browser versions generally provide more reliable WebAssembly support
and will run Pyodide faster, so their use is recommended.
```

**Tier 2** browsers are known to work, but they are not systematically tested in
Pyodide,

| Browser | Minimal supported version | Release date      |
| ------- | ------------------------- | ----------------- |
| Safari  | 14.0                      | 15 September 2020 |
| Edge    | 80                        | 26 February 2020  |

Other browsers with WebAssembly support might also work however they are not
officially supported.

## Web Workers

By default, WebAssembly runs in the main browser thread, and it can make UI
non-responsive for long-running computations.

To avoid this situation, one solution is to run {ref}`Pyodide in a WebWorker <using_from_webworker>`.

## Node.js

As of version 0.18.0 Pyodide can experimentally run in Node.js.

Install the [Pyodide npm package](https://www.npmjs.com/package/pyodide),

```
npm install pyodide
```

Download and extract Pyodide packages from [GitHub
releases](https://github.com/pyodide/pyodide/releases)
(**pyodide-build-\*.tar.bz2** file). The version of the release needs to match
exactly the version of this package.

Then you can load Pyodide in Node.js as follows,

```js
let pyodide_pkg = await import("pyodide/pyodide.js");

let pyodide = await pyodide_pkg.loadPyodide();

await pyodide.runPythonAsync("1+1");
```

```{note}
To start Node.js REPL with support for top level await, use `node --experimental-repl-await`.
```

```{warning}
Download of packages from PyPI is currently not cached when run in
Node.js. Packages will be re-downloaded each time `micropip.install` is run.

For this same reason, installing Pyodide packages from the CDN is explicitly not supported for now.
```

```{eval-rst}
.. toctree::
   :hidden:

   webworker.md
   loading-custom-python-code.md
   file-system.md
```
