(downloading_deploying)=

# Downloading and deploying Pyodide

## Downloading Pyodide

### CDN

Pyodide packages, including the `pyodide.js` file, are available from the JsDelivr CDN,

| channel             | indexURL                                         | Comments                                                                                 | REPL                                               |
| ------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Latest release      | `https://cdn.jsdelivr.net/pyodide/v0.18.0/full/` | Recommended, cached by the browser                                                       | [link](https://pyodide.org/en/stable/console.html) |
| Dev (`main` branch) | `https://cdn.jsdelivr.net/pyodide/dev/full/`     | Re-deployed for each commit on main, no browser caching, should only be used for testing | [link](https://pyodide.org/en/latest/console.html) |

To access a particular file, append the file name to `indexURL`. For instance,
`"${indexURL}pyodide.js"` in the case of `pyodide.js`.

```{warning}
The previous CDN `pyodide-cdn2.iodide.io` is deprecated and should not be used.
```

### Github releases

You can also download Pyodide packages from [Github
releases](https://github.com/pyodide/pyodide/releases)
(`pyodide-build-*.tar.bz2` file) serve them yourself, as explained in the
following section.

=(serving_pyodide_packages)

## Serving Pyodide packages

If you built your Pyodide distribution or downloaded the release tarball
you need to serve Pyodide files with appropriate headers.

### Serving locally

With Python 3.7.5+ you can serve Pyodide files locally by starting

```
python -m http.server
```

from the Pyodide distribution folder.

Point your WebAssembly aware browser to
[http://localhost:8000/console.html](http://localhost:8000/console.html) and open
your browser console to see the output from Python via Pyodide!

### Remote deployments

Any solution that is able to host static files and correctly sets WASM
MIME type, and CORS headers would work. For instance, you can use Github Pages
or similar services.

For additional suggestions for optimizing size and load times, see the [Emscripten
documentation about deployments](https://emscripten.org/docs/compiling/Deploying-Pages.html).
