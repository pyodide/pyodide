(using_from_webworker)=

# Using Pyodide in a web worker

This document describes how to use Pyodide to execute Python scripts
asynchronously in a web worker.

## Setup

Setup your project to serve `webworker.js`. You should also serve
`pyodide.js`, and all its associated `.asm.js`, `.data`, `.json`, and `.wasm`
files as well, though this is not strictly required if `pyodide.js` is pointing
to a site serving current versions of these files.
The simplest way to serve the required files is to use a CDN,
such as `https://cdn.jsdelivr.net/pyodide`. This is the solution
presented here.

Update the `webworker.js` sample so that it has as valid URL for `pyodide.js`, and sets
{any}`indexURL <globalThis.loadPyodide>` to the location of the supporting files.

In your application code create a web worker `new Worker(...)`,
and attach listeners to it using its `.onerror` and `.onmessage`
methods (listeners).

Communication from the worker to the main thread is done via the `Worker.postMessage()`
method (and vice versa).

[worker onmessage]: https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Using_web_workers#Sending_messages_to_and_from_a_dedicated_worker
[worker onerror]: https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Using_web_workers#Handling_errors

## Detailed example

In this example process we will have three parties involved:

- The **web worker** is responsible for running scripts in its own separate thread.
- The **worker API** exposes a consumer-to-provider communication interface.
- The **consumer**s want to run some scripts outside the main thread, so they don't block the main thread.

### Consumers

Our goal is to run some Python code in another thread, this other thread will
not have access to the main thread objects. Therefore, we will need an API that takes
as input not only the Python `script` we want to run, but also the `context` on which
it relies (some JavaScript variables that we would normally get access to if we
were running the Python script in the main thread). Let's first describe what API
we would like to have.

Here is an example of consumer that will exchange with the web worker, via the worker interface/API `py-worker.js`. It runs the following Python `script` using the provided `context` and a function called `asyncRun()`.

```js
import { asyncRun } from "./py-worker";

const script = `
    import statistics
    from js import A_rank
    statistics.stdev(A_rank)
`;

const context = {
  A_rank: [0.8, 0.4, 1.2, 3.7, 2.6, 5.8],
};

async function main() {
  try {
    const { results, error } = await asyncRun(script, context);
    if (results) {
      console.log("pyodideWorker return results: ", results);
    } else if (error) {
      console.log("pyodideWorker error: ", error);
    }
  } catch (e) {
    console.log(
      `Error in pyodideWorker at ${e.filename}, Line: ${e.lineno}, ${e.message}`,
    );
  }
}

main();
```

Before writing the API, let's first have a look at how the worker operates.
How does our web worker run the `script` using a given `context`.

### Web worker

Let's start with the definition. [A worker][worker api] is:

> A worker is an object created using a constructor (e.g. [Worker()][worker constructor]) that runs a named JavaScript file — this file contains the code that will run in the worker thread; workers run in another global context that is different from the current window. This context is represented by either a DedicatedWorkerGlobalScope object (in the case of dedicated workers - workers that are utilized by a single script), or a SharedWorkerGlobalScope (in the case of shared workers - workers that are shared between multiple scripts).

In our case we will use a single worker to execute Python code without interfering with
client side rendering (which is done by the main JavaScript thread). The worker does
two things:

1. Listen on new messages from the main thread
2. Respond back once it finished executing the Python script

These are the required tasks it should fulfill, but it can do other things. For
example, to always load packages `numpy` and `pytz`, you would insert the line
{any}`await pyodide.loadPackage(['numpy', 'pytz']); <pyodide.loadPackage>` as
shown below:

```js
// webworker.js

// Setup your project to serve `py-worker.js`. You should also serve
// `pyodide.js`, and all its associated `.asm.js`, `.data`, `.json`,
// and `.wasm` files as well:
importScripts("{{PYODIDE_CDN_URL}}pyodide.js");

async function loadPyodideAndPackages() {
  self.pyodide = await loadPyodide();
  await self.pyodide.loadPackage(["numpy", "pytz"]);
}
let pyodideReadyPromise = loadPyodideAndPackages();

self.onmessage = async (event) => {
  // make sure loading is done
  await pyodideReadyPromise;
  // Don't bother yet with this line, suppose our API is built in such a way:
  const { id, python, ...context } = event.data;
  // The worker copies the context in its own "memory" (an object mapping name to values)
  for (const key of Object.keys(context)) {
    self[key] = context[key];
  }
  // Now is the easy part, the one that is similar to working in the main thread:
  try {
    await self.pyodide.loadPackagesFromImports(python);
    let results = await self.pyodide.runPythonAsync(python);
    self.postMessage({ results, id });
  } catch (error) {
    self.postMessage({ error: error.message, id });
  }
};
```

### The worker API

Now that we established what the two sides need and how they operate,
let's connect them using this simple API (`py-worker.js`). This part is
optional and only a design choice, you could achieve similar results
by exchanging message directly between your main thread and the webworker.
You would just need to call `.postMessages()` with the right arguments as
this API does.

```js
const pyodideWorker = new Worker("./dist/webworker.js");

const callbacks = {};

pyodideWorker.onmessage = (event) => {
  const { id, ...data } = event.data;
  const onSuccess = callbacks[id];
  delete callbacks[id];
  onSuccess(data);
};

const asyncRun = (() => {
  let id = 0; // identify a Promise
  return (script, context) => {
    // the id could be generated more carefully
    id = (id + 1) % Number.MAX_SAFE_INTEGER;
    return new Promise((onSuccess) => {
      callbacks[id] = onSuccess;
      pyodideWorker.postMessage({
        ...context,
        python: script,
        id,
      });
    });
  };
})();

export { asyncRun };
```

[worker api]: https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API
[worker constructor]: https://developer.mozilla.org/en-US/docs/Web/API/Worker/Worker

## Caveats

Using a web worker is advantageous because the Python code is run in a separate
thread from your main UI, and hence does not impact your application's
responsiveness.
There are some limitations, however.
At present, Pyodide does not support sharing the Python interpreter and
packages between multiple web workers or with your main thread.
Since web workers are each in their own virtual machine, you also cannot share
globals between a web worker and your main thread.
Finally, although the web worker is separate from your main thread,
the web worker is itself single threaded, so only one Python script will
execute at a time.
