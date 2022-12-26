(downloading_deploying)=

# Downloading and deploying Pyodide

## Downloading Pyodide

### CDN

Pyodide is available from the JsDelivr CDN

| channel             | indexURL                                     | Comments                                                                                 | REPL                                               |
| ------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Latest release      | `{{PYODIDE_CDN_URL}}`                        | Recommended, cached by the browser                                                       | [link](https://pyodide.org/en/stable/console.html) |
| Dev (`main` branch) | `https://cdn.jsdelivr.net/pyodide/dev/full/` | Re-deployed for each commit on main, no browser caching, should only be used for testing | [link](https://pyodide.org/en/latest/console.html) |

### GitHub releases

You can also download Pyodide packages from [GitHub
releases](https://github.com/pyodide/pyodide/releases)
(the `pyodide-build-*.tar.bz2` file).

You will need to serve these files yourself.

(serving_pyodide_packages)=

## Serving Pyodide packages

### Serving locally

With Python 3.7.5+ you can serve Pyodide files locally with `http.server`:

```
python -m http.server
```

from the Pyodide distribution folder. Navigate to
[http://localhost:8000/console.html](http://localhost:8000/console.html) and
the Pyodide repl should load.

### Remote deployments

Any service that hosts static files and that correctly sets the WASM MIME type
and CORS headers will work. For instance, you can use GitHub Pages or similar
services.

For additional suggestions for optimizing the size and load time for Pyodide,
see the [Emscripten documentation about
deployments](https://emscripten.org/docs/compiling/Deploying-Pages.html).
