(using_from_service_worker)=

# Using Pyodide in a service worker

This document describes how to use Pyodide to execute Python scripts in a service worker. Compared to typical web workers, service workers are more related to acting as a network proxy, handling background tasks, and things like caching and offline. See [this article](https://web.dev/workers-overview/#use-cases) for more info.

## Detailed example

For our example, we'll be talking about how we can use a service worker to intercept a fetch call for some data and modify the data. We will have two parties involved:

- The **service worker** which will be intercepting fetch calls for JSON, and modifying the data before returning it
- The **consumer** which will be fetching some JSON data

To keep things simple, all we'll do is add a field to a fetched JSON object, but an example of a more interesting use case is transforming fetched tabular data using numpy, and caching the result before returning it.

Please note that service workers will only work on https and localhost, so you will require a server to be running for this example.

### Setup

Setup your project to serve the service worker script `sw.js`, and the XMLHttpRequest polyfill script `xml-http-request.js`. You should also serve `pyodide.js`, and all its associated `.asm.js`, `.data`, `.json`, and `.wasm`
files as well, though this is not strictly required if `pyodide.js` is pointing
to a site serving current versions of these files.
The simplest way to serve the required files is to use a CDN,
such as `https://cdn.jsdelivr.net/pyodide`.

Update the `sw.js` sample so that it has a valid URL for `pyodide.js`, and sets
{any}`indexURL <globalThis.loadPyodide>` to the location of the supporting files.

You'll also need to serve `data.json`, a JSON file containing a simple object - a sample is provided below:

```json
{
  "name": "Jem"
}
```

### Consumer

In our consumer, we want to register our service worker - in the html below, we're registering a classic-type service worker. For convenience, we also provide a button that fetches data and logs it.

```html
<!DOCTYPE html>
<html>
  <head>
    <script>
      /* UPDATE PATHS TO POINT TO YOUR ASSETS */
      const SERVICE_WORKER_PATH = "/sw.js";
      const JSON_FILE_PATH = "./data.json";
      /* IF USING MODULE-TYPE SERVICE WORKER, REPLACE THESE OPTIONS */
      const REGISTRATION_OPTIONS = {
        scope: "/",
      };

      // modified snippet from https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers
      async function registerServiceWorker() {
        if ("serviceWorker" in navigator) {
          try {
            const registration = await navigator.serviceWorker.register(
              SERVICE_WORKER_PATH,
              REGISTRATION_OPTIONS
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

1. Polyfill `XMLHttpRequest` because it isn't available in service workers' global scopes.
2. Import Pyodide
3. If you're planning on calling `loadPyodide` after [installation](https://web.dev/service-worker-lifecycle/) of the service worker, import `pyodide.asm.js` too.

After all the required scripts are imported, we call `loadPyodide` to set up Pyodide, then create a Python function called `modify_data`. This function add a `count` property to an object, where `count` is equal to the number of times `modify_data` is called. We will access this function via a handle assigned to the Javascript variable `modifyData`. We also set up a fetch event handler that intercepts requests for json files so that any JSON object that is fetched is modified using `modifyData`.

```js
/* sw.js */
/* MODIFY IMPORT PATHS TO POINT TO YOUR SCRIPTS, REPLACE IF USING MODULE-TYPE WORKER */
importScripts("./xml-http-request.js");
importScripts("./pyodide.js");
// importScripts("./pyodide.asm.js"); // if loading Pyodide after installation phase, you'll need to import this too

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
        counter += 1
        dict = data.to_py()
        dict['count'] = counter
        return dict
    `,
    { globals: namespace }
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
        Promise.reject("Python code isn't set up yet, try again in a bit")
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
                })
              )
            );
            // Craft the new JSON response
            return new Response(result, {
              headers: { "Content-Type": "application/json" },
            });
          })
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

### XMLHttpRequest polyfill

This script should be imported into your service worker, to assign `XMLHttpRequest` in the service worker's global scope.

```js
/* xml-http-request.js */
/* vendored from https://github.com/apple502j/xhr-shim/blob/master/src/index.js and modified */

const sHeaders = Symbol("headers");
const sRespHeaders = Symbol("response headers");
const sAbortController = Symbol("AbortController");
const sMethod = Symbol("method");
const sURL = Symbol("URL");
const sMIME = Symbol("MIME");
const sDispatch = Symbol("dispatch");
const sErrored = Symbol("errored");
const sTimeout = Symbol("timeout");
const sTimedOut = Symbol("timedOut");
const sIsResponseText = Symbol("isResponseText");

const XMLHttpRequestShim = class XMLHttpRequest extends EventTarget {
  constructor() {
    super();
    this.readyState = this.constructor.UNSENT;
    this.response = null;
    this.responseType = "";
    this.responseURL = "";
    this.status = 0;
    this.statusText = "";
    this.timeout = 0;
    this.withCredentials = false;
    this[sHeaders] = Object.create(null);
    this[sHeaders].accept = "*/*";
    this[sRespHeaders] = Object.create(null);
    this[sAbortController] = new AbortController();
    this[sMethod] = "";
    this[sURL] = "";
    this[sMIME] = "";
    this[sErrored] = false;
    this[sTimeout] = 0;
    this[sTimedOut] = false;
    this[sIsResponseText] = true;
  }
  static get UNSENT() {
    return 0;
  }
  static get OPENED() {
    return 1;
  }
  static get HEADERS_RECEIVED() {
    return 2;
  }
  static get LOADING() {
    return 3;
  }
  static get DONE() {
    return 4;
  }
  get responseText() {
    if (this[sErrored]) return null;
    if (this.readyState < this.constructor.HEADERS_RECEIVED) return "";
    if (this[sIsResponseText]) return this.response;
    throw new DOMException(
      "Response type not set to text",
      "InvalidStateError"
    );
  }
  get responseXML() {
    throw new Error("XML not supported");
  }
  [sDispatch](evt) {
    const attr = `on${evt.type}`;
    if (typeof this[attr] === "function") {
      this.addEventListener(evt.type, this[attr].bind(this), {
        once: true,
      });
    }
    this.dispatchEvent(evt);
  }
  abort() {
    this[sAbortController].abort();
    this.status = 0;
    this.readyState = this.constructor.UNSENT;
  }
  open(method, url) {
    this.status = 0;
    this[sMethod] = method;
    this[sURL] = url;
    this.readyState = this.constructor.OPENED;
  }
  setRequestHeader(header, value) {
    header = String(header).toLowerCase();
    if (typeof this[sHeaders][header] === "undefined") {
      this[sHeaders][header] = String(value);
    } else {
      this[sHeaders][header] += `, ${value}`;
    }
  }
  overrideMimeType(mimeType) {
    this[sMIME] = String(mimeType);
  }
  getAllResponseHeaders() {
    if (this[sErrored] || this.readyState < this.constructor.HEADERS_RECEIVED)
      return "";
    return Object.entries(this[sRespHeaders])
      .map(([header, value]) => `${header}: ${value}`)
      .join("\r\n");
  }
  getResponseHeader(headerName) {
    const value = this[sRespHeaders][String(headerName).toLowerCase()];
    return typeof value === "string" ? value : null;
  }
  send(body = null) {
    if (this.timeout > 0) {
      this[sTimeout] = setTimeout(() => {
        this[sTimedOut] = true;
        this[sAbortController].abort();
      }, this.timeout);
    }
    const responseType = this.responseType || "text";
    this[sIsResponseText] = responseType === "text";
    fetch(this[sURL], {
      method: this[sMethod] || "GET",
      signal: this[sAbortController].signal,
      headers: this[sHeaders],
      credentials: this.withCredentials ? "include" : "same-origin",
      body,
    })
      .finally(() => {
        this.readyState = this.constructor.DONE;
        clearTimeout(this[sTimeout]);
        this[sDispatch](new CustomEvent("loadstart"));
      })
      .then(
        async (resp) => {
          this.responseURL = resp.url;
          this.status = resp.status;
          this.statusText = resp.statusText;
          const finalMIME =
            this[sMIME] || this[sRespHeaders]["content-type"] || "text/plain";
          Object.assign(this[sRespHeaders], resp.headers);
          switch (responseType) {
            case "text":
              this.response = await resp.text();
              break;
            case "blob":
              this.response = new Blob([await resp.arrayBuffer()], {
                type: finalMIME,
              });
              break;
            case "arraybuffer":
              this.response = await resp.arrayBuffer();
              break;
            case "json":
              this.response = await resp.json();
              break;
          }
          this[sDispatch](new CustomEvent("load"));
        },
        (err) => {
          let eventName = "abort";
          if (err.name !== "AbortError") {
            this[sErrored] = true;
            eventName = "error";
          } else if (this[sTimedOut]) {
            eventName = "timeout";
          }
          this[sDispatch](new CustomEvent(eventName));
        }
      )
      .finally(() => this[sDispatch](new CustomEvent("loadend")));
  }
};

self.XMLHttpRequest = XMLHttpRequestShim;
```

## Using module-type service workers

While classic-type service workers have better cross-browser compatibility at the moment, module-type service workers make it easier to include external libraries in your service workers via ES module imports. There are environments where we can safely assume ES module support in service workers, such as Chromium-based browser extensions' background scripts. With the adjustments outlined below, you should be able to use our example with a module-type service worker.

### Setup

Serve `pyodide.mjs` instead of `pyodide.js`, the rest of the setup remains the same.

### Consumers

We need to use different registration options on the consumer side. Replace this section of the script:

```js
/* IF USING MODULE-TYPE SERVICE WORKER, REPLACE THESE OPTIONS */
const REGISTRATION_OPTIONS = {
  scope: "/",
};
```

With the following:

```js
const REGISTRATION_OPTIONS = {
  scope: "/",
  // Note that specifying the type option can cause errors if the browser doesn't support module-type service workers
  type: "module",
};
```

### Service worker

On the service worker side, we need to change the way we import scripts. Replace the importScripts calls shown below:

```js
/* sw.js */
/* MODIFY IMPORT PATHS TO POINT TO YOUR SCRIPTS, REPLACE IF USING MODULE-TYPE WORKER */
importScripts("./xml-http-request.js");
importScripts("./pyodide.js");
// importScripts("./pyodide.asm.js"); // if loading Pyodide after installation phase, you'll need to import this too
```

With the following imports:

```js
/* sw.js */
/* MODIFY IMPORT PATHS TO POINT TO YOUR SCRIPTS */
import "./xml-http-request.js";
import "./pyodide.asm.js"; // This is compulsory in a module-type service worker, which cannot use importScripts
import { loadPyodide } from "./pyodide.mjs"; // Note the .mjs extension
```
