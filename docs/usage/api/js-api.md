# JavaScript API

Backward compatibility of the API is not guaranteed at this point.

## Globals

```{eval-rst}
.. js-doc-summary:: globalThis

.. js-doc-content:: globalThis
```

(js-api-pyodide)=

## pyodide

```{eval-rst}
.. js-doc-summary:: pyodide

.. js-doc-content:: pyodide
```

(js-api-pyodide-ffi)=

## pyodide.ffi

To import types from `pyodide.ffi` you can use for example

```js
import type { PyProxy } from "pyodide/ffi";
```

```{eval-rst}
.. js-doc-summary:: pyodide.ffi

.. js-doc-content:: pyodide.ffi
```

(js-api-pyodide-canvas)=

## pyodide.canvas

This provides APIs to set a canvas for rendering graphics.

```{eval-rst}
.. js-doc-summary:: pyodide.canvas

.. js-doc-content:: pyodide.canvas
```
