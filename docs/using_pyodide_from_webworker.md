# Using Pyodide from a web worker

This document describes how to use pyodide to execute python scripts
asynchronously in a web worker.

## Startup

Setup your project to server `webworker.js`. You should also serve
`pyodide.js`, and all its associated `.asm.js`, `.data`, `.json`, and `.wasm`
files as well, though this is not strictly required if `pyodide.js` is pointing
to a site serving current versions of these files. (Currently the default URL
of https://iodide.io/pyodide-demo/ contains outdated versions).

Update `webworker.js` so that it has as valid URL for `pyodide.js`, and sets
`self.languagePluginUrl` to the location of the supporting files.

In your application code create a web worker, and add listeners for `onerror`
and `onmessage`.

Call `postMessage` on your web worker, passing and object with the key `python`
containing the script to execute as a string. You may pass other keys in the
data object. By default the web worker assigns these to its global scope so that
they may be imported from python. The results are returned as the `results` key,
or if an error was encountered, it is returned in the `error` key.

For example:

```
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
