# JavaScript API

Backward compatibility of the API is not guaranteed at this point.

## Globals

```{eval-rst}
.. js:autosummary:: globalThis

.. js:automodule:: globalThis
```

(js-api-pyodide)=

## pyodide

```{eval-rst}
.. js:autosummary:: pyodide

.. js:automodule:: pyodide
```

(js-api-pyodide-ffi)=

## pyodide.ffi

Foreign function interface classes. Can be used for typescript type annotations
or at runtime for `instanceof` checks.

To import types from `pyodide.ffi` you can use for example

```ts
import type { PyProxy } from "pyodide/ffi";
```

If you want to do an instance check, you'll need to access the type via the
Pyodide API returned from {js:func}`~globalThis.loadPyodide`:

```js
const pyodide = loadPyodide();
const result = pyodide.runPython("... code here");
if (result instanceof pyodide.ffi.PyProxy) {
  // Do something
}
```

```{eval-rst}
.. js:autosummary:: pyodide.ffi

.. js:automodule:: pyodide.ffi
```

(js-api-pyodide-canvas)=

## pyodide.canvas

This provides APIs to set a canvas for rendering graphics.

For example, you need to set a canvas if you want to use the SDL library. See
{ref}`using-sdl` for more information.

```{eval-rst}
.. js:autosummary:: pyodide.canvas

.. js:automodule:: pyodide.canvas
```
