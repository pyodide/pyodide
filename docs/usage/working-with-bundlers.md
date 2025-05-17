(working-with-bundlers)=

# Working with Bundlers

When using Pyodide with bundlers, there are two main approaches:

1. **Loading from a CDN** - This is the simplest approach and sufficient for most use cases
2. **Bundling Pyodide files** - For applications that need to work offline or have specific hosting requirements

## Using Pyodide from a CDN

For most applications, the simplest approach is to use Pyodide from a CDN by setting the `indexURL` parameter:

```js
import { loadPyodide, version as pyodideVersion } from "pyodide";

async function initPyodide() {
  const pyodide = await loadPyodide({
    indexURL: `https://cdn.jsdelivr.net/pyodide/v${pyodideVersion}/full/`
  });
  return pyodide;
}
```

This approach works with most bundlers without additional configuration and is recommended for most users.

## Bundling Pyodide Files

If you need to bundle all Pyodide files with your application (for offline use or self-hosting), follow the instructions below for your specific bundler.

### Webpack

There is a [Pyodide Webpack Plugin][] to load Pyodide from a local bundle in a Webpack project.

### Vite

```{note}
The following instructions have been tested with Pyodide 0.26.2, Vite 5.4.9, and
vite-plugin-static-copy 2.0.0.
```

First, install the Pyodide and vite-plugin-static-copy npm packages:

```
$ npm install pyodide vite-plugin-static-copy
```

Then, in your `vite.config.mjs` file, exclude Pyodide from [Vite's dependency
pre-bundling][optimizedeps] by setting `optimizeDeps.exclude` and ensure that
all Pyodide files will be available in `dist/assets` for production builds by
using a Vite plugin:

```js
import { defineConfig } from "vite";
import { viteStaticCopy } from "vite-plugin-static-copy";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const PYODIDE_EXCLUDE = [
  "!**/*.{md,html}",
  "!**/*.d.ts",
  "!**/*.whl",
  "!**/node_modules",
];

export function viteStaticCopyPyodide() {
  const pyodideDir = dirname(fileURLToPath(import.meta.resolve("pyodide")));
  return viteStaticCopy({
    targets: [
      {
        src: [join(pyodideDir, "*")].concat(PYODIDE_EXCLUDE),
        dest: "assets",
      },
    ],
  });
}

export default defineConfig({
  optimizeDeps: { exclude: ["pyodide"] },
  plugins: [viteStaticCopyPyodide()],
});
```

You can test your setup with this `index.html` file:

```html
<!doctype html>
<html lang="en">
  <head>
    <title>Vite + Pyodide</title>
    <script type="module" src="main.mjs"></script>
  </head>
</html>
```

And this `src/main.mjs` file:

```js
import { loadPyodide } from "pyodide";

async function hello_python() {
  let pyodide = await loadPyodide();
  return pyodide.runPythonAsync("1+1");
}

hello_python().then((result) => {
  console.log("Python says that 1+1 =", result);
});
```

If you need to specify a specific path for the bundled files, you can set the `indexURL` parameter:

```js
let pyodide = await loadPyodide({
  indexURL: "/assets"  // Path to the directory containing pyodide.js and other files
});
```

Make sure this works both in Vite's dev mode:

```
npx vite
```

And as a production build:

```
npx vite build
npx vite preview
```

[optimizedeps]: https://vitejs.dev/guide/dep-pre-bundling.html
[pyodide webpack plugin]: https://github.com/pyodide/pyodide-webpack-plugin
