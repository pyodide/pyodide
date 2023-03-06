(using-sdl)=

# Using SDL-based packages in Pyodide

```{admonition} This is experimental
:class: warning

SDL support in Pyodide is experimental.
```

Pyodide provides a way to use SDL-based packages in the browser,
This document explains how to use SDL-based packages in Pyodide.

## Setting canvas

Before using SDL-based packages, you need to set the canvas to draw on.
Pyodide provides following APIs to set, unset, and get the canvas:

```js
pyodide.SDL.setCanvas(canvas);
pyodide.SDL.unsetCanvas();
pyodide.SDL.getCanvas();
```

The `canvas` object must be a
[HTMLElement](https://developer.mozilla.org/ko/docs/Web/API/HTMLElement) object.
For example, you can set a canvas like this:

```js
let sdl2Canvas = document.createElement("canvas");
pyodide.SDL.setCanvas(sdl2Canvas);
```
