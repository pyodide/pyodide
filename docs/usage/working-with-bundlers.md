(working-with-bundlers)=

# Working with Bundlers

## Webpack

There is a [Pyodide Webpack Plugin][] to load Pyodide from a CDN in a Webpack
project.

## Vite

```{note}
The following instructions have been tested with Pyodide 0.25.0 and Vite 5.1.4.
```

If you have installed Pyodide via npm, you can use it in Vite as follows. First,
the Pyodide npm package currently uses [`node-fetch`][] to load some files,
which does not work in a browser; to resolve this, install the
[`isomorphic-fetch`][] package so that Pyodide does not try to load `node-fetch`
in the browser:

```
$ npm install --save isomorphic-fetch@^3
```

Then, exclude Pyodide from [Vite's dependency pre-bundling][optimizedeps] by
setting `optimizeDeps.exclude` in your `vite.config.js` file:

```js
import { defineConfig } from "vite";

export default defineConfig({ optimizeDeps: { exclude: ["pyodide"] } });
```

You can test your setup with this `index.html` file:

```html
<!doctype html>
<html>
  <head>
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

This should be sufficient for Vite dev mode:

```
$ npx vite
```

For a production build, you must also manually make sure that all Pyodide files
will be available in `dist/assets`, by first copying them to `public/assets`
before building:

```
$ mkdir -p public/assets/
$ cp node_modules/pyodide/* public/assets/
$ npx vite build
```

Then you can view this production build to verify that it works:

```
$ npx vite preview
```

[`isomorphic-fetch`]: https://www.npmjs.com/package/isomorphic-fetch
[`node-fetch`]: https://www.npmjs.com/package/node-fetch
[optimizedeps]: https://vitejs.dev/guide/dep-pre-bundling.html
[pyodide webpack plugin]: https://github.com/pyodide/pyodide-webpack-plugin
