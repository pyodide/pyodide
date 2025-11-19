# Pyodide Platform ABI

## ABIs

### General

#### Building for the Emscripten target

To build C/C++ projects, use emscripten compiler toolchain `emcc`.

To build Rust projects, use `rustc --target wasm32-unknown-emscripten` or
`cargo build --target wasm32-unknown-emscripten`. When building, `emcc` must be
on the path or linking will fail.

#### Making a shared library

Emscripten shared libraries use the [the WebAssembly binary
format](https://webassembly.github.io/spec/core/binary/index.html) and have a
[dynamic linking section](https://github.com/WebAssembly/tool-conventions/blob/main/DynamicLinking.md).

`emcc` will ignore the `-shared` flag. To make a shared library with `emcc`, you
must pass `-sSIDE_MODULE=1` or `-sSIDE_MODULE=2`.

To make a shared library with `rustc`, pass `-C link-arg=-sSIDE_MODULE=2`. To
build a shared library with `cargo`, put `-C link-arg=-sSIDE_MODULE=2` in the
`RUSTFLAGS` environment variable.

#### No pthreads support

`-pthread` must not be used at compile or link time. If `-pthread` is used, the
resulting libraries will not load.

#### Controlling the Set of Exported Symbols

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

#### Libraries Linked to the Interpreter

Pyodide is statically linked with the following libraries:

- `libegl.js`
- `libeventloop.js`
- `libGL`
- `libhtml5_webgl.js`
- `libhtml5.js`
- `liblz4`
- `libsdl.js`
- `libwebgl.js`
- `libwebsocket.js`
- `bzip2`
- `zlib`

All of these come from Emscripten ports and the versions of these libraries are
determined by the version of Emscripten we build with. Any symbols from these
static libraries may be used by shared libraries.

### pyodide_2024_0

By default, all builds of the Pyodide runtime with Python 3.12 will use the
`pyodide_2024_0` abi.

The Emscripten version is 3.1.58.

#### WASM_BIGINT

All shared libraries must be linked with `-sWASM_BIGINT`.

Since Rust 1.84.0 or nightly 2024-11-05, Rust will automatically pass
`-Clink-arg=-sWASM_BIGINT`. In earlier versions of Rust it was required to pass
`-Clink-arg=-sWASM_BIGINT` explicitly. Passing it explicitly will work in all
cases.

#### Unwinding ABIs

By default, C++ libraries are built with exceptions disabled, and `throw` is an
abort. The same is true for `setjmp`/`longjmp`. To enable exceptions and
`setjmp`/`longjmp`, `-fexceptions` must be passed at compile time and link time.

Rust will automatically enable unwinding.

#### Runtime Library Loading Path

Specifying an RPATH is not supported, `emcc` will warn and ignore it. The
dynamic loader has been patched so that all dynamic libraries in a wheel named
`wheel_name-<tag>.whl` will be loaded as if
`/lib/python3.12/site-packages/wheel_name.libs` is on the `RPATH`, so any
dynamic library dependencies should be placed in the wheel in a folder called
`wheel_name.libs`.

### pyodide_2025_0 (under development)

By default, all builds of the Pyodide runtime with Python 3.13 will use the
`pyodide_2025_0` abi.

This section reflects the aspirational ABI for `pyodide_2025_0`. This is all
subject to change without notice.

The Emscripten version is 4.0.9.

#### WASM_BIGINT

Since Emscripten 4.0.0, `-sWASM_BIGINT` is the default.

#### Unwinding ABIs

By default, C++ libraries are built with exceptions disabled, and `throw` is an
abort. The same is true for `setjmp`/`longjmp`. To enable exceptions and
`setjmp`/`longjmp`, `-fexceptions` must be passed at compile time and link time.

The flag `-Z emscripten-wasm-eh` must be passed to Rust. It is necessary to use
a Rust nightly after January 15th, 2025, when the `-Z emscripten-wasm-eh` flag
was added. All `-Z` flags are gated nightly-only. The `-Z emscripten-wasm-eh`
flag will never be stabilized but eventually it will switch to being on by
default and then be removed. See
[the Rust Major Change Propoisal](https://github.com/rust-lang/compiler-team/issues/801)
for more information.

##### The Rust sysroot

Rust ships with an Emscripten sysroot built without the `-Z emscripten-wasm-eh`
flag so using the standard sysroot will lead to linker errors due to mismatched
unwinding ABIs.

Some crates can be built with

```
RUSTFLAGS=-Zemscripten-wasm-eh cargo build -Zbuild-std
```

If the crate uses `panic=abort` it may be possible to build with

```
cargo build -Z build-std=std,panic_abort -Z build-std-features=panic_immediate_abort
```

but it won't work with any crates that use `cargo vendor` and there seem to be
various bugs. Also, when building a large number of packages `-Zbuild-std`
inefficiently rebuilds the standard library for each crate.

If not building with `-Zbuild-std`, it is possible to get a compatible sysroot
from
[pyodide/rust-emscripten-wasm-eh-sysroot](https://github.com/pyodide/rust-emscripten-wasm-eh-sysroot).
This is only distributed for Rust nightly-2025-02-01. To use a different Rust
nightly, it is possible to clone the `pyodide/rust-emscripten-wasm-eh-sysroot`
repository and follow the instructions in the README to build a compatible
sysroot. To install the Emscripten sysroot use:

```sh
rustup toolchain install nightly-2025-02-01
TOOLCHAIN_ROOT=$(rustup run nightly-2025-02-01 rustc --print sysroot)
RUSTLIB=$TOOLCHAIN_ROOT/lib/rustlib
wget https://github.com/pyodide/rust-emscripten-wasm-eh-sysroot/releases/download/emcc-4.0.9_nightly-2025-02-01/emcc-4.0.9_nightly-2025-02-01.tar.bz2
tar -xf emcc-4.0.9_nightly-2025-02-01.tar.bz2 --directory=$RUSTLIB
```

Note that this is all necessary _even if_ the crate uses `-Cpanic=abort` because
the Rust standard library is not built with `-Cpanic=abort` and so there will be
linker errors due to pulling in symbols from the standard library that use the
wrong unwinding ABI.

#### Runtime Library Loading Path

There is full support for `RPATH`. The dynamic loader will only load
dependencies that are properly specified on the `RPATH`, just being in
`/lib/python3.14/site-packages/wheel_name.libs` is not sufficient.

## ABI-sensitive flags

This non-normative section gives some background on why the ABIs described above
were chosen.

### `-pthread`

Pyodide has no support for pthreads. The interaction between pthreads and
dynamic linking is slow and buggy, more work upstream would be required to
support them together. It's possible to build the Python interpreter with
dynamic linking disabled and pthreads enabled, but of course there would be
no need to specify the ABI of such an interpreter.

### `-sWASM_BIGINT`

When WebAssembly was first introduced, the JS/WebAssembly interface had to
support for functions with 64 bit integer arguments or return values. Such
functions were impossible to call from JavaScript. Every exported function with
any 64 bit integer types needed to get a legalizer wrapper that split the 64 bit
types into two 32 bit integers. This meant also that each function had a pair of
function pointers, one to the original function and a second one to the
legalizer. A table had to be maintained to allow conversion between the
legalizer wrapper and the original function. Numerous Emscripten bugs exist due
to code paths that fail to correctly handle this distinction.

The [JS BigInt Integration](https://github.com/WebAssembly/JS-BigInt-integration)
proposal added support for calling such functions directly, using `BigInt` for
the 64 bit integer types. It has been fully supported in all browsers since
Safari 15 was released on September 20, 2021.

The `-sWASM_BIGINT` linker setting makes Emscripten assume that the JS runtime
supports JS BigInt Integration and so it will not export legalizers. This option
must match between the main executable and dynamic libraries or the dynamic
libraries will fail to load.

The `-sWASM_BIGINT` linker setting is applied by default since Emscripten 4.0.0.
As a result, it is applied by default on `pyodide_2025_0` and above.

### `-fexceptions` vs `-fwasm-exceptions`

When WebAssembly was first introduced, it had no intrinsics for unwinding the
stack, as is required for C++ exceptions, Rust panics, and `setjmp`/`longjmp`.
Emscripten offered support for "JavaScript Exception handling" via the
`-fexceptions` flag. Emscripten used JavaScript `throw` to throw exceptions and
replaced the bodies of all try blocks with a separate function which is called
via a JavaScript trampoline that calls the try body in a try catch block. So the
following code:

```C++
int f() {
    int x;
    int y;
    try {
        x = g();
        y = h();
    } catch(...) {
        // ...
    }
}
```

is roughly transformed by the compiler to:

```C++
void try_body(int *x, int *y) {
    *x = g();
    *y = h();
}

thread_local uintptr_t __THREW__ = 0;
thread_local int __threwValue = 0;

int f() {
    int x;
    int y;
    invoke_vii(&try_body, x, y);
    if (__THREW__) {
        // inspect __threwValue and execute appropriate catch body here
    }
}
```

And `invoke_vii` is defined as a JavaScript function roughly like:

```js
function invoke_vii(fptr, a1, a2) {
  var sp = stackSave();
  try {
    getWasmTableEntry(fptr)(a1, a2);
  } catch (e) {
    stackRestore(sp);
    _setThrew();
  }
}
```

All of this is complicated and is a common source of bugs and incompatibility.
[The WebAssembly Exception Handling proposal](https://github.com/WebAssembly/exception-handling/)
added WebAssembly intrinsics for exception handling which has been universally
supported since Safari 15.2 was released on December 13, 2021. Stack unwinding
with WebAssembly Exception handling is faster, has smaller code sizes, and has
fewer bugs.

However, Rust did not support WebAssembly Exception handling so we were unable
to use it. Stack switching does not work through JavaScript trampolines, and
JavaScript Exception handling normally uses JavaScript exception handling. To
work around this, we wrote
[rather elaborate code](https://github.com/pyodide/pyodide/blob/0.27.4/src/core/stack_switching/create_invokes.mjs)
to implement the JavaScript exception handling ABI using WebAssembly exceptions.

Thankfully, nowadays
[Rust does support WebAssembly exception handling](https://github.com/rust-lang/compiler-team/issues/801)
and the `pyodide_2025_0` ABI and later will rely on it.
