(working-with-bundlers)=

# Working with Bundlers

## Webpack

There is a [Pyodide Webpack Plugin][] to load Pyodide from a CDN in a Webpack
project.

## Vite

```{note}
The following instructions have been tested with Pyodide 0.26.2, Vite 5.4.9, and
vite-plugin-pyodide 2.0.0.
```

First, install the Pyodide and vite-plugin-pyodide npm packages:

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
