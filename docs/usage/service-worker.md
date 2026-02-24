(using_from_service_worker)=

# Using Pyodide in a service worker

This document describes how to use Pyodide to execute Python scripts in a
service worker. Compared to typical web workers, service workers are more
related to acting as a network proxy, handling background tasks, and things like
caching and offline. See [this
article](https://web.dev/workers-overview/#use-cases) for more info.

## Detailed example

For our example, we'll be talking about how we can use a service worker to
intercept a fetch call for some data and modify the data. We will have two
parties involved:

- The **service worker** which will be intercepting fetch calls for JSON, and
  modifying the data before returning it
- The **consumer** which will be fetching some JSON data

To keep things simple, all we'll do is add a field to a fetched JSON object, but
an example of a more interesting use case is transforming fetched tabular data
using numpy, and caching the result before returning it.

Please note that service workers will only work on https and localhost, so you
will require a server to be running for this example.

### Setup

You serve
`pyodide.mjs`, and all its associated `.asm.mjs`, `.json`, and `.wasm`
files as well, though this is not strictly required if `pyodide.mjs` is pointing
to a site serving current versions of these files. The simplest way to serve the
required files is to use a CDN, such as `https://cdn.jsdelivr.net/pyodide`.

Update the `sw.js` sample so that it has a valid URL for `pyodide.mjs`, and sets
{js:func}`indexURL <exports.loadPyodide>` to the location of the supporting
files.

You'll also need to serve `data.json`, a JSON file containing a simple object -
a sample is provided below:

```json
{
  "name": "Jem"
}
```

### Consumer

In our consumer, we want to register our service worker as a module-type worker.
For convenience, we also provide a button that fetches data and logs it.

```html
<!doctype html>
<html>
  <head>
    <script>
      /* UPDATE PATHS TO POINT TO YOUR ASSETS */
      const SERVICE_WORKER_PATH = "/sw.js";
      const JSON_FILE_PATH = "./data.json";
      const REGISTRATION_OPTIONS = {
        scope: "/",
        type: "module",
      };

      // modified snippet from
      // https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers
      async function registerServiceWorker() {
        if ("serviceWorker" in navigator) {
          try {
            const registration = await navigator.serviceWorker.register(
              SERVICE_WORKER_PATH,
              REGISTRATION_OPTIONS,
            );
            if (registration.installing) {
              console.log("Service worker installing");
            } else if (registration.waiting) {
              console.log("Service worker installed");
            } else if (registration.active) {
              console.log("Service worker active");
            }
          } catch (error) {
            console.error(`Registration failed with ${error}`);
          }
        }
      }

      async function fetchAndLogData() {
        try {
          console.log(await (await fetch(JSON_FILE_PATH)).json());
        } catch (e) {
          console.error("Failed to fetch", e);
        }
      }

      registerServiceWorker();
    </script>
  </head>

  <body>
    <button onclick="fetchAndLogData()">Fetch and log data</button>
  </body>
</html>
```

### Service worker

To set up Pyodide in a service worker, you'll need to do the following:
1. Statically import `pyodide.asm.mjs` pass the default export to `loadPyodide` as `_createPyodideModule` option.
   Norally, `pyodide.asm.mjs` is dynamically imported by `loadPyodide`, but service workers forbid dynamic `import()`,
   so `loadPyodide` cannot load it automatically. Therefore, we need to pass the default export of `pyodide.asm.mjs` to `loadPyodide` as `_createPyodideModule` option.
2. Import `loadPyodide` from `pyodide.mjs`
After all the required scripts are imported, we call `loadPyodide` to set up
Pyodide, then create a Python function called `modify_data`. This function add a
`count` property to an object, where `count` is equal to the number of times
`modify_data` is called. We will access this function via a handle assigned to
the Javascript variable `modifyData`. We also set up a fetch event handler that
intercepts requests for json files so that any JSON object that is fetched is
modified using `modifyData`.
```js
/* sw.js */
/* MODIFY IMPORT PATHS TO POINT TO YOUR SCRIPTS */
// Service workers forbid dynamic import(), so we statically import
// pyodide.asm.mjs and set the escape hatch that loadPyodide checks first.
import _createPyodideModule from "./pyodide.asm.mjs";
import { loadPyodide } from "./pyodide.mjs";

let modifyData;
let pyodide;
loadPyodide({ _createPyodideModule }).then((_pyodide) => {
  pyodide = _pyodide;
  let namespace = pyodide.globals.get("dict")();

  pyodide.runPython(
    `
    import json

    counter = 0
    def modify_data(data):
        global counter
        counter += 1
        dict = data.to_py()
        dict['count'] = counter
        return dict
    `,
    { globals: namespace },
  );

  // assign the modify_data function from the Python context to a Javascript variable
  modifyData = namespace.get("modify_data");
  namespace.destroy();
});

self.addEventListener("fetch", (event) => {
  if (event.request.url.endsWith("json")) {
    if (!modifyData) {
      // For this example, throw so it's clear that the worker isn't ready to modify responses
      // This is because we don't want to return a response that isn't modified yet
      // If your service worker would return the same response as a server (eg. it's just performing calculations closer to home)
      // then you may want to let the event through without doing anything
      event.respondWith(
        Promise.reject("Python code isn't set up yet, try again in a bit"),
      );
    } else {
      event.respondWith(
        // We aren't using the async await syntax because event.respondWith needs to respond synchronously
        // it can't be executing after an awaited promise within the fetch event handler, otherwise you'll get this
        // Uncaught (in promise) DOMException: Failed to execute 'respondWith' on 'FetchEvent': The event has already been responded to
        fetch(event.request)
          .then((v) => v.json())
          .then((originalData) => {
            let proxy = modifyData(originalData);
            let pyproxies = [];

            // Because toJs gives us a Map, we transform it to a plain Javascript object before changing it to JSON
            let result = JSON.stringify(
              Object.fromEntries(
                proxy.toJs({
                  pyproxies,
                }),
              ),
            );
            // Craft the new JSON response
            return new Response(result, {
              headers: { "Content-Type": "application/json" },
            });
          }),
      );
    }
  }
});

// Code below is for easy iteration during development, you may want to remove or modify in a prod environment:

// Immediately become the active service worker once installed, so we don't have a stale service worker intercepting requests
// You can remove this code and achieve a similar thing by enabling "Update on Reload" in devtools, if supported:
// https://web.dev/service-worker-lifecycle/#update-on-reload
self.addEventListener("install", function () {
  self.skipWaiting();
});

// With this, we won't need to reload the page before the service worker can intercept fetch requests
// https://developer.mozilla.org/en-US/docs/Web/API/Clients/claim#examples
self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});
```
