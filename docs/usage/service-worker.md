(using_from_service_worker)=

# Using Pyodide in a service worker

This document describes how to use Pyodide to execute Python scripts in a service worker. Compared to typical web workers, service workers are more related to acting as a network proxy, handling background tasks, and things like caching and offline. See [this article](https://web.dev/workers-overview/#use-cases) for more info.

For our example, we'll be talking about how we can use a service worker to intercept a fetch call for some data and modify the data. We will have two parties involved:

- The **service worker** which will be intercepting fetch calls for JSON, and modifying the data before returning it
- The **consumer** which will be fetching some JSON data

To keep things simple, all we'll do is add a field to a fetched JSON object, but an example of a more interesting use case is transforming fetched tabular data using numpy, and caching the result before returning it.

You might notice we have two different examples on this page. There are two different kinds of service workers, classic and module. For cross-browser compatibility, it might be easier to use classic service workers for now, as Firefox doesn't yet support module-type service workers. That said, module-type service workers may be a better fit if you want to write background service workers for Chromium-based browser extensions.

## Detailed example 1 - classic service workers

### Setup

Setup your project to serve `classic-service-worker.js`. You should also serve
`pyodide.js`, and all its associated `.asm.js`, `.data`, `.json`, and `.wasm`
files as well, though this is not strictly required if `pyodide.js` is pointing
to a site serving current versions of these files.
The simplest way to serve the required files is to use a CDN,
such as `https://cdn.jsdelivr.net/pyodide`. This is the solution
presented here.

Update the `classic-service-worker.js` sample so that it has a valid URL for `pyodide.js`, and sets
{any}`indexURL <globalThis.loadPyodide>` to the location of the supporting files.

You'll also need to serve `data.json`, a JSON file containing a simple object - a sample is provided below:

```json
{
  "name": "Jem"
}
```

### Consumers

HTML:

```html
<!doctype html>
<html>
  <head>
    <script>
      /* MODIFY PATHS TO POINT TO YOUR ASSETS */
      const SERVICE_WORKER_PATH = "/classic-service-worker.js";
      const JSON_FILE_PATH = "./data.json";
      const REGISTRATION_OPTIONS = {
        scope: "/",
      };

      // modified snippet from https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers
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

```js
/* MODIFY IMPORT PATHS TO POINT TO YOUR SCRIPTS */
importScripts("./xml-http-request.js"); // This script should assign self.XMLHttpRequest to a compatible polyfill, there are many on npm
importScripts("./pyodide.asm.js"); // This is necessary if you choose to load pyodide after installation of the service worker
importScripts("./pyodide.js");

let modifyData;
let pyodide;
loadPyodide({}).then((_pyodide) => {
  pyodide = _pyodide;
  let namespace = pyodide.globals.get("dict")();

  pyodide.runPython(
    `
    import json

    counter = 0
    def modify_data(data):
        global counter
        dict = data.to_py()
        dict['count'] = counter
        counter += 1
        return dict
    `,
    { globals: namespace },
  );

  // assign the modify_data function from the Python context to our Javascript variable
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
            // Craft our new JSON response
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

## Detailed example 2 - module service workers

### Setup

Setup your project to serve `module-service-worker.js`. You should also serve
`pyodide.js`, and all its associated `.asm.js`, `.data`, `.json`, and `.wasm`
files as well, though this is not strictly required if `pyodide.js` is pointing
to a site serving current versions of these files.
The simplest way to serve the required files is to use a CDN,
such as `https://cdn.jsdelivr.net/pyodide`. This is the solution
presented here.

Update the `module-service-worker.js` sample so that it has a valid URL for `pyodide.js`, and sets
{any}`indexURL <globalThis.loadPyodide>` to the location of the supporting files.

You'll also need to serve `data.json`, a JSON file containing a simple object - a sample is provided below:

```json
{
  "name": "Jem"
}
```

### Consumers

HTML:

```html
<!doctype html>
<html>
  <head>
    <script>
      /* MODIFY PATHS TO POINT TO YOUR ASSETS */
      const SERVICE_WORKER_PATH = "/module-service-worker.js";
      const JSON_FILE_PATH = "./data.json";
      const REGISTRATION_OPTIONS = {
        scope: "/",
        // Note that specifying the type option can cause errors if the browser doesn't support module-type service workers
        type: "module",
      };

      // modified snippet from https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers
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

This example is largely the same as the classic service worker example above, the main difference is how we import things. `importScripts` is not supported in module-type workers, we use the ESM import instead.

```js
/* MODIFY IMPORT PATHS TO POINT TO YOUR SCRIPTS */
import "./xml-http-request.js"; // This script should assign self.XMLHttpRequest to a compatible polyfill, there are many on npm
import "./pyodide.asm.js"; // Pyodide detects this and skips dynamically importing it. Dynamic imports fail in a service worker.
import { loadPyodide } from "./pyodide.mjs";

let modifyData;
let pyodide;
loadPyodide({}).then((_pyodide) => {
  pyodide = _pyodide;
  let namespace = pyodide.globals.get("dict")();

  pyodide.runPython(
    `
    import json

    counter = 0
    def modify_data(data):
        global counter
        dict = data.to_py()
        dict['count'] = counter
        counter += 1
        return dict
    `,
    { globals: namespace },
  );

  // assign the modify_data function from the Python context to our Javascript variable
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
            // Craft our new JSON response
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
