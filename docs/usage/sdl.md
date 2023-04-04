(using-sdl)=

# Using SDL-based packages in Pyodide

```{admonition} This is experimental
:class: warning

SDL support in Pyodide is experimental.
Pyodide relies on undocumented behavior of Emscripten and SDL,
so it may break or change in the future.

In addition, this feature requires to enable an opt-in flag,
`pyodide._api._skip_unwind_fatal_error = true;`
which can lead to stack unwinding issues (see {ref}`sdl-known-issues`).
```

Pyodide provides a way to use SDL-based packages in the browser,
This document explains how to use SDL-based packages in Pyodide.

## Setting canvas

Before using SDL-based packages, you need to set the canvas to draw on.

The `canvas` object must be a
[HTMLCanvasElement](https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement) object,
with the `id` attribute set to `"canvas"`.
For example, you can set a canvas like this:

```js
let sdl2Canvas = document.createElement("canvas");
sdl2Canvas.id = "canvas";
pyodide.canvas.setCanvas2D(sdl2Canvas);
```

See also: {ref}`js-api-pyodide-canvas`

(sdl-known-issues)=

## Known issues

There is a known issue that with,

```
pyodide._api._skip_unwind_fatal_error = true;
```

Python call stacks are not being unwound after calling `emscripten_set_main_loop()`.

see: [pyodide#3697](https://github.com/pyodide/pyodide/issues/3697)
