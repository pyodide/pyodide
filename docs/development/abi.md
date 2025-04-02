# Pyodide Platform ABI

## ABIs

### General

Shared libraries must be linked with `-sSIDE_MODULE=1` or

```
-sSIDE_MODULE=2 -sEXPORTED_FUNCTIONS=<export list>
```

Note that the name of each symbol in the list needs to be prefixed with an
underscode. For the smallest result, it is recommended to link with:

```
-sSIDE_MODULE=2 -sEXPORTED_FUNCTIONS=["_PyInit_MyCModule1", "_PyInit_MyCModule2]
```

To force all symbols to be exported, link with `-sSIDE_MODULE=1`.

If `-pthread` is used at compile or link time, the resulting libraries will not
load.

To compile Rust packages, the following flags must be passed to `rustc`:

```
-C link-arg=-sSIDE_MODULE=2 -C link-arg=-sWASM_BIGINT
```

When not invoking `rustc` directly, for instance when using cargo, set these
into the `RUSTFLAGS` environment variable.

Compiling with `-sSIDE_MODULE=1` will not work with Rust because Rust libraries
contain a `lib.rmeta` file which is not an object file. Rust produces the
correct list of exported symbols automatically so this should not be a problem
in practice.

On Rust libc versions older than 0.2.162, it may be necessary to pass
`-Z link-native-libraries=no` as a `RUSTFLAG`.

### pyodide_2024_0

The Emscripten version is 3.1.58. The Python version is 3.12. Python 3.12 must
be used at build time. All shared libraries must be linked with `-sWASM_BIGINT`.

By default, C++ libraries are built with exceptions disabled, and `throw` is an
abort. The same is true for `setjmp`/`longjmp`. To enable exceptions and
`setjmp`/`longjmp`, `-fexceptions` must be passed at compile time and link time.

Specifying an RPATH is not supported and will cause link errors. The dynamic
loader has been patched so that all dynamic libraries in a wheel named
`wheel_name-<tag>.whl` will be loaded as if
`/lib/python3.12/site-packages/wheel_name.libs` is on the `RPATH`, so any
dynamic library dependencies should be placed in the wheel in a folder called
`wheel_name.libs`.

### pyodide_2025_0 (under development)

This section reflects the aspirational ABI for `pyodide_2025_0`. This is all
subject to change without notice.

The Emscripten version is 4.0.6. The Python version is 3.13. Python 3.13 must be
used at build time.

By default, C++ libraries are built with exceptions disabled, and `throw` is an
abort. The same is true for `setjmp`/`longjmp`. To enable exceptions and
`setjmp`/`longjmp`, `-fwasm-exceptions` must be passed at compile time and link time.

There is full support for `RPATH`. The dynamic loader will only load
dependencies that are properly specified on the `RPATH`, just being in
`/lib/python3.13/site-packages/wheel_name.libs` is not sufficient.

For building Rust, it is necessary to use a Rust nightly after January 15th, 2025.
The flag `-Z emscripten-wasm-eh` must be passed. It is also necessary to use a
compatible emscripten sysroot that has been built with wasm exception handling.
Such sysroots are produced and distributed by
[pyodide/rust-emscripten-wasm-eh-sysroot](https://github.com/pyodide/rust-emscripten-wasm-eh-sysroot).
This is only distributed for Rust nightly-2025-02-01. To use a different Rust
nighly, it is possible to clone the `pyodide/rust-emscripten-wasm-eh-sysroot`
repository and follow the instructions in the README to build a compatible
sysroot. To install the emscripten sysroot use:

```sh
rustup toolchain install nightly-2025-02-01
TOOLCHAIN_ROOT=$(rustup which --toolchain nightly-2025-02-01 rustc)
RUSTLIB=$TOOLCHAIN_ROOT/lib/rustlib
wget https://github.com/pyodide/rust-emscripten-wasm-eh-sysroot/releases/download/emcc-4.0.6_nightly-2025-02-01/emcc-4.0.6_nightly-2025-02-01.tar.bz2
tar -xf emcc-4.0.6_nightly-2025-02-01.tar.bz2 --directory=$RUSTLIB
```

Note that this is all necessary _even if_ the crate uses `-Cpanic=abort` because
the Rust standard library is not built with `-Cpanic=abort` and so there will be
linker errors due to pulling in symbols from the standard library that use the
wrong unwinding ABI.

## ABI sensitive flags

### `-pthread`

Pyodide has no support for pthreads.

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
and the `pyodide_2025` abi will rely on it.
