(using-sdl)=

# Using SDL-based packages in Pyodide

```{admonition} This is experimental
:class: warning

SDL support in Pyodide and Emscripten is experimental.
Things *will* not work as expected, and you will need to
do some workarounds to make it work.
```

Pyodide provides a way to use SDL-based packages in the browser,
but it is not as easy as using other packages. This document explains
how to use SDL-based packages in Pyodide.

## Setting canvas

SDL-based packages require a canvas to draw on.
Emscripten uses the `canvas` attribute of the `Module` object to
determine the canvas to draw on. This is not set by default in Pyodide,
so you need to set it manually.

```js
const pyodide = loadPyodide();

let sdl2Canvas = document.createElement("canvas");
sdl2Canvas.id = "canvas";
sdl2Canvas.tabindex = -1;
pyodide._module.canvas = sdl2Canvas;
```

## Handling events

SDL-based packages like `pygame` or `pyxel` require keyboard and mouse
events to work. Unfortunately, these events need to be handled in
JavaScript, and passed to the Python code. Since every package has
different event handling mechanism, you will need to figure out how
to handle and pass events for each package.

See the example how [pyxel](https://github.com/kitao/pyxel/blob/3b49279ad892e5c22016494fc539900c427c621e/wasm/pyxel.js)
does it.
