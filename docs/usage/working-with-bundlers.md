(working-with-bundlers)=

# Working with Bundlers

## Webpack

There is a [Pyodide Webpack Plugin][] to load Pyodide from a CDN in a Webpack
project.

## Vite

```{note}
The following instructions have been tested with Pyodide 0.26.0 and Vite 5.2.13.
```

First, install the Pyodide npm package:

```
$ npm install pyodide
```

Then, in your `vite.config.js` file, exclude Pyodide from [Vite's dependency
pre-bundling][optimizedeps] by setting `optimizeDeps.exclude` and ensure that
all Pyodide files will be available in `dist/assets` for production builds by
using a Vite plugin:

```js
import { defineConfig } from "vite";
import { copyFile, mkdir } from "fs/promises";
import { join } from "path";

export default defineConfig({
  optimizeDeps: { exclude: ["pyodide"] },
  plugins: [
    {
      name: "vite-plugin-pyodide",
      generateBundle: async () => {
        const assetsDir = "dist/assets";
        await mkdir(assetsDir, { recursive: true });
        const files = [
          "pyodide-lock.json",
          "pyodide.asm.js",
          "pyodide.asm.wasm",
          "python_stdlib.zip",
        ];
        for (const file of files) {
          await copyFile(
            join("node_modules/pyodide", file),
            join(assetsDir, file),
          );
        }
      },
    },
  ],
});
```

You can test your setup with this `index.html` file:

```html
<!doctype html>
<html lang="en">
  <head>
    <title>Vite + Pyodide</title>
    <script type="module" src="/src/main.js"></script>
  </head>
</html>
```

And this `src/main.js` file:

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
