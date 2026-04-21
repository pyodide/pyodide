# ABI-sensitive flags

## `-pthread`

Pyodide has no support for pthreads. The interaction between pthreads and
dynamic linking is slow and buggy, more work upstream would be required to
support them together. It's possible to build the Python interpreter with
dynamic linking disabled and pthreads enabled, but of course there would be
no need to specify the ABI of such an interpreter.

## `-sWASM_BIGINT`

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

## `-fexceptions` vs `-fwasm-exceptions`

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
