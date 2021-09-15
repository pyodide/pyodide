# Using Pyodide

Pyodide may be used in any context where you want to run Python inside a web
browser or a backend JavaScript environment.

## Web browsers

To use Pyodide on a web page you need to load `pyodide.js` and initialize
Pyodide with {any}`loadPyodide` specifying a index URL for packages:

```html-pyodide
<!DOCTYPE html>
<html>
  <head>
      <script src="https://cdn.jsdelivr.net/pyodide/v0.18.1/full/pyodide.js"></script>
  </head>
  <body>
    <script type="text/javascript">
      async function main(){
        let pyodide = await loadPyodide({
          indexURL : "https://cdn.jsdelivr.net/pyodide/v0.18.1/full/"
        });
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
 - `cdn.jsdelivr.net/npm/pyodide@0.18.1/` is a mirror of the Pyodide NPM package, which includes none of the WASM files
```

## Web Workers

By default, WebAssembly runs in the main browser thread, and it can make UI non
responsive for long running computations.

To avoid this situation, one solution is to run {ref}`Pyodide in a WebWorker <using_from_webworker>`.

## Node.js

As of version 0.18.0 Pyodide can experimentally run in Node.js.

Install the [Pyodide npm package](https://www.npmjs.com/package/pyodide),

```
npm install pyodide
```

Download and extract Pyodide packages from [Github
releases](https://github.com/pyodide/pyodide/releases)
(**pyodide-build-\*.tar.bz2** file). The version of the release needs to match
exactly the version of this package.

Then you can load Pyodide in Node.js as follows,

```js
let pyodide_pkg = await import("pyodide/pyodide.js");

let pyodide = await pyodide_pkg.loadPyodide({
  indexURL: "<pyodide artifacts folder>",
});

await pyodide.runPythonAsync("1+1");
```

```{note}
To start Node.js REPL with support for top level await, use `node --experimental-repl-await`.
```

```{warning}
Download of packages from PyPi is currently not cached when run in
Node.js. Packages will be re-downloaded each time `micropip.install` is run.

For this same reason, installing Pyodide packages from the CDN is explicitly not supported for now.
```

```{eval-rst}
.. toctree::
   :hidden:

   webworker.md
```
