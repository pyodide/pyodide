# Using Pyodide

Pyodide may be used in a web browser or a backend JavaScript environment.

## Web browsers

To use Pyodide in a web page you need to load `pyodide.js` and initialize
Pyodide with {any}`loadPyodide <globalThis.loadPyodide>`.

```html-pyodide
<!doctype html>
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

See the {ref}`quickstart` for a walk-through tutorial as well as
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

It's also possible to run {ref}`Pyodide in a Service Worker <using_from_service_worker>`.

If you're not sure whether you need web workers or service workers, here's an [overview and comparison of the two](https://web.dev/workers-overview/).

## Node.js

```{note}
The following instructions have been tested with Node.js 18.5.0. To use
Pyodide with older versions of Node, you might need to use  additional command line
arguments, see below.
```

It is now possible to install the
[Pyodide npm package](https://www.npmjs.com/package/pyodide) in Node.js. To
follow these instructions you need at least Pyodide 0.21.0.
You can explicitly ask npm to use
the alpha version:

```
$ npm install "pyodide@>=0.21.0-alpha.2"
```

Once installed, you can run the following simple script:

```js
// hello_python.js
const { loadPyodide } = require("pyodide");

async function hello_python() {
  let pyodide = await loadPyodide();
  return pyodide.runPythonAsync("1+1");
}

hello_python().then((result) => {
  console.log("Python says that 1+1 =", result);
});
```

```
$ node hello_python.js
Loading distutils
Loaded distutils
Python initialization complete
Python says that 1+1= 2
```

Or you can use the REPL. To start the Node.js REPL with support for top level
await, use `node --experimental-repl-await`:

```
$ node --experimental-repl-await
Welcome to Node.js v18.5.0.
Type ".help" for more information.
> const { loadPyodide } = require("pyodide");
undefined
> let pyodide = await loadPyodide();
Loading distutils
Loaded distutils
Python initialization complete
undefined
> await pyodide.runPythonAsync("1+1");
2
```

### Node.js versions <0.17

- `Node.js` versions 14.x and 16.x: to use certain features of Pyodide you
  need to manually install `node-fetch`, e.g. by doing `npm install node-fetch`.

- `Node.js v14.x`: you need to pass the option `--experimental-wasm-bigint`
  when starting Node. Note that this flag is not documented by `node --help`
  and moreover, if you pass `--experimental-wasm-bigint` to node >14 it is an
  error:

```
$ node -v
v14.20.0

$ node --experimental-wasm-bigint hello_python.js
warning: no blob constructor, cannot create blobs with mimetypes
warning: no BlobBuilder
Loading distutils
Loaded distutils
Python initialization complete
Python says that 1+1= 2
```

```{eval-rst}
.. toctree::
   :hidden:

   webworker.md
   loading-custom-python-code.md
   file-system.md
   service-worker.md
```
