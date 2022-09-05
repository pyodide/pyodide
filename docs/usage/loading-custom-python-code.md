(loading-custom-python-code)=

# Loading custom Python code

Pyodide provides a simple API {any}`pyodide.runPython` to run Python code.
However, when your Python code grow bigger, putting hundreds of lines inside `runPython` is not scalable.

For larger projects, the best way to run Python code with Pyodide is:

1. create a Python package
1. load your Python package into the Pyodide (Emscripten) virtual file system
1. import the package with `let mypkg = pyodide.pyimport("mypkgname")`
1. call into your package with `mypkg.some_api(some_args)`.

## Using wheels

The best way of serving custom Python code is making it a package in the wheel (.whl) format.
If the package is built as a `wheel` file, you can use {any}`micropip.install` to
install the package. See {ref}`loading_packages` for more information.

```{admonition} Packages with C extensions
:class: warning

If your Python code contains C extensions,
it needs to be built in a specialized way (See {ref}`new-packages`).
```

## Loading then importing Python code

It is also possible to download and import Python code from an external source.
We recommend that you serve all files in an archive, instead of individually downloading each Python script.

### From Python

```pyodide
// Downloading an archive
await pyodide.runPythonAsync(`
    from pyodide.http import pyfetch
    response = await pyfetch("https://.../your_package.tar.gz") # .zip, .whl, ...
    await response.unpack_archive() # by default, unpacks to the current dir
`)
pkg = pyodide.pyimport("your_package");
pkg.do_something();
```

```pyodide
// Downloading a single file
await pyodide.runPythonAsync(`
    from pyodide.http import pyfetch
    response = await pyfetch("https://.../script.py")
    with open("script.py", "wb") as f:
        f.write(await response.bytes())
`)
pkg = pyodide.pyimport("script");
pkg.do_something();
```

```{admonition} What is pyfetch?
:class: info

Pyodide provides {any}`pyodide.http.pyfetch`,
which is a convenient wrapper of JavaScript `fetch`.
See {ref}`load-external-files-in-pyodide` for more information.
```

### From JavaScript

```js
let response = await fetch("https://.../your_package.tar.gz"); // .zip, .whl, ...
let buffer = await response.arraybuffer();
await pyodide.unpackArchive(buffer); // by default, unpacks to the current dir
pyodide.pyimport("your_package");
```

```{admonition} Warning on unpacking a wheel package
:class: warning

Since a wheel package is actually a zip archive,
you can use {any}`pyodide.unpackArchive()`
to unpack a wheel package, instead of using {any}`micropip.install`.

However, {mod}`micropip` does dependency resolution when installing packages,
while {any}`pyodide.unpackArchive()` simply unpacks the archive.
So you must be aware of that each dependencies of a package need to be installed manually
before unpacking a wheel.

> _Future plans:_ we are planning to support a method for a static dependency resolution
(See: [pyodide#2045](https://github.com/pyodide/pyodide/issues/2045)).
```

## Running external code directly

If you want to run a single Python script from an external source in a simplest way,
you can:

```js
pyodide.runPython(await (await fetch("https://some_url/.../code.py")).text());
```
