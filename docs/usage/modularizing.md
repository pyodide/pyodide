
(modularizing-python-codes)=
# Modularizing Python codes

Pyodide provides a simple API {any}`pyodide.runPython` to run Python code.
However, when your Python codes grow bigger, putting hundreds of lines inside `runPython` is not scalable.

The best way to run Python code with Pyodide is:

1. write a Python package
1. load your Python package into the Pyodide (Emscripten) virtual file system
1. import the package with ``let mypkg = pyodide.pyimport("mypkgname")``
1. call into your package with ``mypkg.some_api(some_args)``.

## How to load a Python package into the virtual file system

If the package is built as a `wheel` file, use {any}`micropip.install` to
install the package.

```pyodide
await pyodide.loadPackage("micropip");
await pyodide.runPythonAsync(`
  import micropip
  await micropip.install("https://.../your_package.whl")
`)
let pkg = pyodide.pyimport("your_package");
pkg.do_something(...);

// or

pyodide.runPython(`
    import your_package
    your_package.do_something(...)
`)
```

If the package is a single Python file or an archive, use {any}`pyodide.http.pyfetch` to
download it.

```pyodide
// Single file
await pyodide.runPythonAsync(`
    from pyodide.http import pyfetch
    response = await pyfetch("https://.../script.py")
    with open("script.py", "wb") as f:
        f.write(await response.bytes())
`)
pkg = pyodide.pyimport("script");
pkg.do_something();
```

```pyodide
// Archive
await pyodide.runPythonAsync(`
    from pyodide.http import pyfetch
    response = await pyfetch("https://.../your_package.tar.gz")
    await response.unpack_archive()
`)
pkg = pyodide.pyimport("your_package");
pkg.do_something();
```

```{admonition} How can I prefetch package files before loading Pyodide
:class: info

If you want to prefetch package files before loading Pyodide,
you can use JS `fetch` to download packages.
After fetching packages, Pyodide provides {any}`pyodide.unpackArchive()` to save them
into the Pyodide virtual file system.

```js
let response = await fetch("https://.../your_package.tar.gz"); // .zip, .whl, ...
let buffer = await response.arraybuffer();
// ... initialize Pyodide
await pyodide.unpackArchive(buffer);
pyodide.pyimport("your_package");
```

```{admonition} Warning on unpacking a wheel package
:class: warning

Since a wheel package is actually a zip archive,
you can use {any}`pyodide.unpackArchive()`
to unpack a wheel package, instead of using {any}`micropip.install`.

However, {any}`micropip` does dependency resolution when installing packages,
while {any}`pyodide.unpackArchive()` simply unpacks the archive.
So you must be aware of that each dependencies of a package need to be installed manually
before unpacking a wheel.

> _Future plans:_ we are planning to support a method for a static dependency resolution
(See: [pyodide#2045](https://github.com/pyodide/pyodide/issues/2045)).
```