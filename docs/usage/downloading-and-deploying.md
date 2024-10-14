(downloading_deploying)=

# Downloading and deploying Pyodide

## Downloading Pyodide

### CDN

Pyodide is available from the JsDelivr CDN

| channel             | indexURL                                     | Comments                                                                                 | REPL                                               |
| ------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Latest release      | `{{PYODIDE_CDN_URL}}`                        | Recommended, cached by the browser                                                       | [link](https://pyodide.org/en/stable/console.html) |
| Dev (`main` branch) | `https://cdn.jsdelivr.net/pyodide/dev/full/` | Re-deployed for each commit on main, no browser caching, should only be used for testing | [link](https://pyodide.org/en/latest/console.html) |

For a given version, several build variants are also available,

- `<version>/full/`: the default full build
- `<version>/debug/`: build with unminified `pyodide.asm.js` useful for debugging

### GitHub releases

You can also download Pyodide packages from [GitHub
releases](https://github.com/pyodide/pyodide/releases). The full distribution
including all vendored packages is available as `pyodide-{{VERSION}}.tar.bz2`.
The full distribution is quite large (200+ megabytes). The minimal set of files
needed to start Pyodide is included as `pyodide-core-{{VERSION}}.tar.bz2`. It is
intended for use with node which will automatically install missing packages
from the cdn -- it is the same set of files that are installed if you use `npm
install pyodide`. It may also be convenient for other purposes.

You will need to serve these files yourself.

(serving_pyodide_packages)=

## Serving Pyodide packages

### Serving locally

With Python 3.7.5+ you can serve Pyodide files locally with {py:mod}`http.server`:

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

## Contents of Pyodide Github releases

### Files in `pyodide-core-{{VERSION}}.tar.bz2`

| File Name         | Description                                                                                                                                                                                                                                       |
| :---------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| pyodide.asm.js    | The JavaScript half of the main "binary". Direct output from the Emscripten compiler. Contains the Emscripten bootstrap code + all JavaScript libraries used by C + the JavaScript/Wasm runtime interop APIs.                                     |
| pyodide.asm.wasm  | The WebAssembly half of the main "binary". Direct output from the Emscripten compiler. Contains all C library code that is statically linked. Also includes enough of libcxx to support things like exceptions in extension modules that use C++. |
| pyodide.js        | Exports loadPyodide on globalThis. Legacy support for people who can't use es6 modules for whatever reason. Prefer pyodide.mjs.                                                                                                                   |
| pyodide.mjs       | A small JS loader shim which exports loadPyodide. It manages downloading the runtime and handling user settings.                                                                                                                                  |
| python_stdlib.zip | The Python Standard Library for pyodide. A zip file consisting of the Python Lib folder (except a few things we've unvendored) and the Pyodide Python runtime libraries. Mounted directly into the Pyodide FS and imported using ZipImporter.     |
| package.json      | Tells node how to use Pyodide, since pyodide-core was primarily intended for use with node.                                                                                                                                                       |
| pyodide-lock.json | Lockfile for Python packages, used by pyodide.loadPackage and micropip.install. Necessary in all cases.                                                                                                                                           |

### Additional Files in `pyodide-{{VERSION}}.tar.bz2`

| File Name       | Description                                                                                                                                                                                          |
| :-------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| fonts/          | Used by matplotlib-pyodide.                                                                                                                                                                          |
| ffi.d.ts        | Typescript type definitions, useful if you want to use Pyodide in a typescript project.                                                                                                              |
| pyodide.d.ts    | Typescript type definitions, useful if you want to use Pyodide in a typescript project.                                                                                                              |
| \*.whl          | Contains various Python Wheels like NumPy, Pandas, SciPy, etc. When downloading and including in a project, these no longer need to be loaded from Pyodide's online wheel repository during runtime. |
| \*.metadata     | Information about the included wheels, such as name, author, license, dependencies, etc. Allows more efficient package resolution, specified in [PEP 658](https://peps.python.org/pep-0658/).        |
| \*.zip          | These are shared libraries and unvendored Python standard library modules.                                                                                                                           |
|                 |
| python          | Bash/node polyglot. Only needed for node < 18.                                                                                                                                                       |
| pyodide.js.map  | Source maps to improve tracebacks. Not really that useful to people outside of the project, probably should be only included in debug builds.                                                        |
| pyodide.mjs.map | Source maps to improve tracebacks. Not really that useful to people outside of the project, probably should be only included in debug builds.                                                        |
| \*-tests.tar    | Unvendored tests from wheels. If a wheel includes a test folder, we take them out and put them here.                                                                                                 |
| console.html    | The Pyodide repl.                                                                                                                                                                                    |
