(using_from_webworker)=

# Using Pyodide in a web worker

This document includes an example demonstrating how to use Pyodide to execute
Python scripts asynchronously in a web worker.

Let's start with [the definition of a worker][worker api].

> A worker is an object created using a constructor (e.g. [Worker()][worker constructor])
> that runs a named JavaScript file — this file contains the code
> that will run in the worker thread; workers run in another global context that
> is different from the current window.

A lot of Python programs do long-running synchronous computations. Running them
in the main thread blocks the UI. Using a web worker is advantageous because the
Python code runs in a separate thread from your UI and does not impact your
application's responsiveness.

On the other hand, since workers run in a separate global context, you cannot
directly share globals between a worker and the main thread. In particular, a
worker cannot directly manipulate the DOM.

## Detailed example

In this example process we will have three parties involved:

- The **web worker** is responsible for running scripts in its own separate thread.
- The **worker API** exposes a consumer-to-provider communication interface.
- The **consumer**s want to run some scripts outside the main thread, so they
  don't block the main thread.

### Consumers

Our goal is to run some Python code in another thread. This other thread will
not have access to the main thread objects. Therefore, we will need an API that
takes as input both the Python `script` we want to run and the `context` on
which it relies (some JavaScript variables that our code needs access to). Let's
first describe what API we would like to have.

Here is an example of consumer that will exchange with the web worker, via
`workerApi.mjs`. It runs the following Python `script` using the provided
`context` and a function called `asyncRun()`.

```js
import { asyncRun } from "./workerApi.js";

const script = `
    import statistics
    statistics.stdev(A_rank)
`;

const context = {
  A_rank: [0.8, 0.4, 1.2, 3.7, 2.6, 5.8],
};

async function main() {
  const { result, error } = await asyncRun(script, context);
  if (result) {
    console.log("pyodideWorker result:", result);
  } else if (error) {
    console.log("pyodideWorker error:", error);
  }
}

main();
```

Before writing the API, let's first have a look at how the worker runs the
`script` using a given `context`.

### Web worker

Here is the worker code:

```js
// webworker.mjs
import { loadPyodide } from "{{PYODIDE_CDN_URL}}pyodide.mjs";

let pyodideReadyPromise = loadPyodide();

self.onmessage = async (event) => {
  // make sure loading is done
  const pyodide = await pyodideReadyPromise;
  const { id, python, context } = event.data;
  // Now load any packages we need, run the code, and send the result back.
  await pyodide.loadPackagesFromImports(python);
  // make a Python dictionary with the data from `context`
  const dict = pyodide.globals.get("dict");
  const globals = dict(Object.entries(context));
  try {
    // Execute the python code in this context
    const result = await pyodide.runPythonAsync(python, { globals });
    self.postMessage({ result, id });
  } catch (error) {
    self.postMessage({ error: error.message, id });
  }
};
```

### The worker API

Now that we established what the two sides need and how they operate, let's
connect them using an API that wraps the message passing code into an
asynchronous function.

```js
// workerApi.mjs
function getPromiseAndResolve() {
  let resolve;
  let promise = new Promise((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

// Each message needs a unique id to identify the response. In a real example,
// we might use a real uuid package
let lastId = 1;
function getId() {
  return lastId++;
}

// Add an id to msg, send it to worker, then wait for a response with the same id.
// When we get such a response, use it to resolve the promise.
function requestResponse(worker, msg) {
  const { promise, resolve } = getPromiseAndResolve();
  const id = getId();
  worker.addEventListener("message", function listener(event) {
    if (event.data?.id !== id) {
      return;
    }
    // This listener is done so remove it.
    worker.removeEventListener("message", listener);
    // Filter the id out of the result
    const { id, ...rest } = data;
    resolve(rest);
  });
  worker.postMessage({ id, ...msg });
  return promise;
}

const pyodideWorker = new Worker("./webworker.mjs", { type: "module" });

export function asyncRun(script, context) {
  return requestResponse(pyodideWorker, {
    context,
    python: script,
  });
}
```

[worker api]: https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API
[worker constructor]: https://developer.mozilla.org/en-US/docs/Web/API/Worker/Worker
