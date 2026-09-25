# The PyEmscripten Platform

(pyodide-platform-abi)=

## What is the PyEmscripten Platform?

The PyEmscripten platform defines a binary interface for an Emscripten
application. If an Emscripten application and an Emscripten shared library are
both built to target this platform, then the application will be able to load
and run the shared library.

To build a shared library that is compatible with a given version of Pyodide, it
is necessary to identify which PyEmscripten platform that version of Pyodide
uses and follow the corresponding shared library build instructions. This allows
wheels to be built for Pyodide that will load and run correctly.

The Emscripten compiler makes no ABI stability guarantees between versions, and
several linker flags can adjust the ABI. Therefore, Python packages built for
Emscripten must match the ABI-sensitive compiler and linker flags used to build
the interpreter to avoid load-time or run-time errors.

To balance ABI stability needs of package maintainers with flexibility to adopt
new platform features and bug fixes, Pyodide adopts a new PyEmscripten platform
for each feature release of Python. The platform tags take the form
`pyemscripten_${YEAR}_${PATCH}_wasm32` (e.g., `pyemscripten_2026_0_wasm32` for
Python 3.14).

Each PyEmscripten platform specifies:

* the version of the Emscripten compiler to be used,
* what libraries are statically linked to the application,
* the stack unwinding ABI to be used,
* how the loader handles dependency lookup, and
* various additional compile and linker flags

The PyEmscripten platform definition does not include anything about Python and
in particular it is agnostic to the Python version it is intended to be used
with. However, for clarity we indicate in the platform documentation which
Python version we plan to use each platform with.

The PyEmscripten platform is specified by {pep}`783`, and wheels using this
tag are supported on PyPI. Prior to {pep}`783`, it was called the Pyodide
platform instead of the PyEmscripten platform (and used the form
`pyodide_${YEAR}_${PATCH}_wasm32`).

### Platform Versions

- [pyemscripten_2026_5](abi/315.md) (Python 3.15)
- [pyemscripten_2026_0](abi/314.md) (Python 3.14)
- [pyemscripten_2025_0](abi/313.md) (Python 3.13)
- [pyemscripten_2024_0](abi/312.md) (Python 3.12)

For background on why specific flags were chosen, see [ABI-sensitive flags](abi/flags.md).

```{eval-rst}
.. toctree::
   :hidden:

   abi/315.md
   abi/314.md
   abi/313.md
   abi/312.md
   abi/flags.md
```

## General

### Building for the Emscripten target

To build C/C++ projects, use the Emscripten compiler toolchain `emcc`.

To build Rust projects, use `rustc --target wasm32-unknown-emscripten` or
`cargo build --target wasm32-unknown-emscripten`. When building, `emcc` must be
on the path or linking will fail.

### Making a shared library

Emscripten shared libraries use the [the WebAssembly binary
format](https://webassembly.github.io/spec/core/binary/index.html) and have a
[dynamic linking section](https://github.com/WebAssembly/tool-conventions/blob/main/DynamicLinking.md).

`emcc` will ignore the `-shared` flag. To make a shared library with `emcc`, you
must pass `-sSIDE_MODULE=1` or `-sSIDE_MODULE=2`.

With Rust version 1.95.0 and later, Rust will automatically detect that the
crate is a cdylib and link an Emscripten shared library. For older Rust
versions, to make a shared library with `rustc`, pass
`-C link-arg=-sSIDE_MODULE=2`. To build a shared library with `cargo`, put
`-C link-arg=-sSIDE_MODULE=2` in the `RUSTFLAGS` environment variable.

### Static Libraries Linked to the Main Binary

Many libraries cannot be dynamically linked on the Emscripten platform, most
frequently because they contain JavaScript code. If they are to be made
available for packages to use, they must be statically linked to the
interpreter. There are also a few libraries that are needed for a Python builtin
module. As a part of the platform definition, we document which versions of
which libraries are linked to the main binary.

### Other Library Dependencies

Other library dependencies should either be statically linked to the extension
module or built as a shared library and vendored into the wheel in a `.libs`
directory. Like on native platforms, the RPATH of the dependent extension module
should also be set as appropriate to ensure that the dependency is resolved
correctly.

### Extension Modules as `dlopen()` Targets

Some packages have a plugin architecture: compiled code inside the package calls
`dlopen()` at runtime on a separately built shared library, and that library
needs symbols defined by the package's own extension module. DuckDB's loadable
extensions work this way.

This does not work by default. Pyodide loads package shared libraries with local
symbol visibility, the equivalent of `RTLD_LOCAL`, so a module's exports do not
reach the shared symbol table that a later, unrelated `dlopen()` call searches.
The `dlopen()` then fails with `Dynamic linking error: cannot resolve symbol
<name>` even though the symbol really is exported by the already-loaded module.

Resolve this the same way native platforms do, by declaring the dependency
rather than relying on global symbol visibility. Link the `dlopen()`-ed library
against the extension module that provides the symbols, so that it records a
`NEEDED` entry in its dynamic linking section, and set an RPATH so that the
dependency can be located at runtime:

```
emcc -sSIDE_MODULE=2 ... \
    -Wl,-rpath,'$ORIGIN/../..' \
    path/to/site-packages/mypkg/_core.cpython-314-wasm32-emscripten.so
```

When the plugin is `dlopen()`-ed, each `NEEDED` entry is resolved against the
RPATH, the providing module is found to be already loaded, and its exports are
merged into the plugin's local scope. The symbols do not become globally
visible, so this does not affect any other module. `$ORIGIN` expands to the
directory of the library that declares the RPATH.

Two consequences are worth planning for:

- A `NEEDED` entry records the exact filename of the providing module. For a
  Python extension module that filename contains the ABI tag, as in
  `_core.cpython-314-wasm32-emscripten.so`, so the plugin is loadable only by
  the Python version it was built against and must be rebuilt when that changes.
- The RPATH must resolve to the same path the providing module was originally
  loaded from, so that the already-loaded module is reused. If it resolves to a
  different path, a second independent copy of the module is instantiated rather
  than an error being raised.

### No pthreads support

`-pthread` must not be used at compile or link time. If `-pthread` is used, the
resulting libraries will not load.

### Controlling the Set of Exported Symbols

All symbols that form part of a binary module's interface must be exported. It
is desirable to produce the minimal list of exported symbols to keep download
size and runtime to a minimum. Not exporting symbols also reduces chances of
symbol collisions.

Linking a shared libraries with `-sSIDE_MODULE=1` will pass `-whole-archive` to
`wasm-ld` and so force inclusion of all object files and all symbols. Linking
with `-sSIDE_MODULE=2` will only include symbols that are explicitly listed with
`-sEXPORTED_FUNCTIONS=<export list>`. The name of each symbol in the list must
be prefixed with an underscore. For the smallest result, it is recommended to
link with:

```
-sSIDE_MODULE=2 -sEXPORTED_FUNCTIONS=["_PyInit_MyCModule1", "_PyInit_MyCModule2]
```
