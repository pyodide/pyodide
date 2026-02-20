# Using Pyodide

Pyodide may be used in a web browser or a backend JavaScript environment.

## Web browsers

To use Pyodide in a web page you need to load `pyodide.js` and initialize
Pyodide with {js:func}`~exports.loadPyodide`.

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
 - `cdn.jsdelivr.net/pyodide/` distributes Python packages built with Pyodide as well
    as `pyodide.js`
 - `cdn.jsdelivr.net/npm/pyodide@0.19.0/` is a mirror of the Pyodide NPM package which
    includes only the Pyodide runtime, not any of the wheels.
```

### Supported browsers

Webassembly support in browsers is evolving very rapidly,
and we recommend using the latest browsers whenever possible
to take full advantage of Pyodide and its webassembly features.
If you are using an older browser, some features may not work properly.

Currently, Pyodide is being tested against the following browser versions,
so we recommend using a browser version at least equal to or higher than these.

| Browser | Version | Release date  |
| ------- | ------- | ------------- |
| Firefox | 112     | 11 April 2023 |
| Chrome  | 112     | 29 March 2023 |
| Safari  | 16.4    | 27 March 2023 |

## Web Workers

By default, WebAssembly runs in the main browser thread, and it can make UI
non-responsive for long-running computations.

To avoid this situation, one solution is to run {ref}`Pyodide in a WebWorker
<using_from_webworker>`.

It's also possible to run {ref}`Pyodide in a Service Worker <using_from_service_worker>`.

If you're not sure whether you need web workers or service workers, here's an [overview and
comparison of the two](https://web.dev/workers-overview/).

## Node.js

```{warning}
Starting with Pyodide 0.25.0, Node.js < 18 is no longer officially supported.
Older versions of Node.js might still work, but they are not tested or guaranteed to work.
```

It is possible to install the [Pyodide npm package](https://www.npmjs.com/package/pyodide) in
Node.js.

```
$ npm install pyodide
```

Once installed, you can run the following simple script:

```js
// hello_python.mjs
import { loadPyodide } from "pyodide";

async function hello_python() {
  let pyodide = await loadPyodide();
  return pyodide.runPythonAsync("1+1");
}

const result = await hello_python();
console.log("Python says that 1+1 =", result);
```

```
$ node hello_python.mjs
Python says that 1+1= 2
```

Or you can use the REPL. To start the Node.js REPL with support for top level
await, use `node --experimental-repl-await`:

```
$ node --experimental-repl-await
Welcome to Node.js v18.5.0.
Type ".help" for more information.
> const { loadPyodide } = await import("pyodide");
undefined
> let pyodide = await loadPyodide();
undefined
> await pyodide.runPythonAsync("1+1");
2
```

```{eval-rst}
.. toctree::
   :hidden:

   loading-custom-python-code.md
   file-system.md
   accessing-files.md
   webworker.md
   service-worker.md
   working-with-bundlers.md
   cli.md
```
