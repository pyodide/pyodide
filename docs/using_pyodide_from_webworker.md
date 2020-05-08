# Using Pyodide from a web worker

This document describes how to use pyodide to execute python scripts
asynchronously in a web worker.

## Startup

Setup your project to serve `webworker.js`. You should also serve
`pyodide.js`, and all its associated `.asm.js`, `.data`, `.json`, and `.wasm`
files as well, though this is not strictly required if `pyodide.js` is pointing
to a site serving current versions of these files.

Update the `webworker.js` sample so that it has as valid URL for `pyodide.js`, and sets
`self.languagePluginUrl` to the location of the supporting files.

In your application code create a web worker, and add listeners for `onerror`
and `onmessage`.

Call `postMessage` on your web worker, passing an object with the key `python`
containing the script to execute as a string. You may pass other keys in the
data object. By default the web worker assigns these to its global scope so that
they may be imported from python. The results are returned as the `results` key,
or if an error was encountered, it is returned in the `error` key.

For example:

```js
var pyodideWorker = new Worker('./webworker.js')

pyodideWorker.onerror = (e) => {
  console.log(`Error in pyodideWorker at ${e.filename}, Line: ${e.lineno}, ${e.message}`)
}

pyodideWorker.onmessage = (e) => {
  const {results, error} = e.data
  if (results) {
    console.log('pyodideWorker return results: ', results)
  } else if (error) {
    console.log('pyodideWorker error: ', error)
  }
}

const data = {
  A_rank: [0.8, 0.4, 1.2, 3.7, 2.6, 5.8],
  python:
    'import statistics\n' +
    'from js import A_rank\n' +
    'statistics.stdev(A_rank)'
}

pyodideWorker.postMessage(data)

```

## Loading packages

Packages referenced from your python script will be automatically downloaded
the first time they are encountered. Please note that some of the larger
packages such as `numpy` or `pandas` may take several seconds to load.
Subsequent uses of these packages will not incur the download overhead of the
first run, but there is still some time required for the `import` in python
itself.

If you would like to pre-load some packages, or the automatic package loading
does not work for you for some reason, you may modify the `webworker.js` source
to load some specific packages as described in
[Using Pyodide directly from Javascript](using_pyodide_from_javascript.md).

For example, to always load packages `numpy` and `pytz`, you would insert the
line `self.pyodide.loadPackage(['numpy', 'pytz']).then(() => {` as shown below:

```js
self.languagePluginUrl = 'http://localhost:8000/'
importScripts('./pyodide.js')

var onmessage = function(e) { // eslint-disable-line no-unused-vars
  languagePluginLoader.then(() => {
    self.pyodide.loadPackage(['numpy', 'pytz']).then(() => {
      const data = e.data;
      const keys = Object.keys(data);
      for (let key of keys) {
        if (key !== 'python') {
          // Keys other than python must be arguments for the python script.
          // Set them on self, so that `from js import key` works.
          self[key] = data[key];
        }
      }
      self.pyodide.runPythonAsync(data.python, () => {})
          .then((results) => { self.postMessage({results}); })
          .catch((err) => {
            // if you prefer messages with the error
            self.postMessage({error : err.message});
            // if you prefer onerror events
            // setTimeout(() => { throw err; });
          });
    });
  });
}
```

## Caveats

Using a web worker is advantageous because the python code is run in a separate
thread from your main UI, and hence does not impact your application's
responsiveness.
There are some limitations, however.
At present, Pyodide does not support sharing the Python interpreter and
packages between multiple web workers or with your main thread.
Since web workers are each in their own virtual machine, you also cannot share
globals between a web worker and your main thread.
Finally, although the web worker is separate from your main thread,
the web worker is itself single threaded, so only one python script will
execute at a time.
