# Pyodide Platform ABI

(pyodide-platform-abi)=

## What is Pyodide Platform ABI?

The Pyodide Platform ABI defines the binary interface that Python extension
modules must follow to be compatible with a specific version of the Pyodide
runtime. This specification ensures that wheels built for Pyodide will load and
run correctly.

The Emscripten compiler makes no ABI stability guarantees between versions, and
several linker flags can adjust the ABI. Therefore, Python packages built for
Emscripten must match the ABI-sensitive compiler and linker flags used to build
the interpreter to avoid load-time or run-time errors.

To balance ABI stability needs of package maintainers with flexibility to adopt
new platform features and bug fixes, Pyodide adopts a new ABI for each feature
release of Python. The platform tags take the form `pyodide_${PYTHON_MAJOR_MINOR}_${PATCH}_wasm32`
(e.g., `pyodide_314_0_wasm32` for Python 3.14).

Each ABI version specifies the CPython version, Emscripten compiler version,
linked libraries, and required compiler/linker flags needed to build compatible
extensions.

> See: [PEP 783](https://peps.python.org/pep-0783/) for the full specification.

### ABI Versions

- [pyodide_314_0](abi/314.md) (Python 3.14, under development)
- [pyodide_2025_0](abi/313.md) (Python 3.13)
- [pyodide_2024_0](abi/312.md) (Python 3.12)

> Before Python 3.14, Pyodide used a different ABI versioning scheme based on the year of release.
> From Python 3.14, Pyodide uses the ABI versioning scheme based on the Python version.

For background on why specific flags were chosen, see [ABI-sensitive flags](abi/flags.md).

```{eval-rst}
.. toctree::
   :hidden:

   abi/314.md
   abi/313.md
   abi/312.md
   abi/flags.md
```

## General

### Building for the Emscripten target

To build C/C++ projects, use emscripten compiler toolchain `emcc`.

To build Rust projects, use `rustc --target wasm32-unknown-emscripten` or
`cargo build --target wasm32-unknown-emscripten`. When building, `emcc` must be
on the path or linking will fail.

### Making a shared library

Emscripten shared libraries use the [the WebAssembly binary
format](https://webassembly.github.io/spec/core/binary/index.html) and have a
[dynamic linking section](https://github.com/WebAssembly/tool-conventions/blob/main/DynamicLinking.md).

`emcc` will ignore the `-shared` flag. To make a shared library with `emcc`, you
must pass `-sSIDE_MODULE=1` or `-sSIDE_MODULE=2`.

To make a shared library with `rustc`, pass `-C link-arg=-sSIDE_MODULE=2`. To
build a shared library with `cargo`, put `-C link-arg=-sSIDE_MODULE=2` in the
`RUSTFLAGS` environment variable.

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

To compile Rust packages, `-C link-arg=-sSIDE_MODULE=2` must be passed to rustc.
Compiling with `-sSIDE_MODULE=1` will not work with Rust because Rust libraries
contain a `lib.rmeta` file which is not an object file. Rust produces the
correct list of exported symbols automatically so this should not be a problem.
