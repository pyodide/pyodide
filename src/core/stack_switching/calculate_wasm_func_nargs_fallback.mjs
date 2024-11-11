// Various function pointer mismatch bugs occur because people declare a
// `METH_NOARGS` function which should take 2 arguments:
// ```
// my_no_arg_meth(PyObject* module, PyObject* always_null);
// ```
// but leave off the `always_null` second argument or both arguments. Similar
// errors occur less frequently with `METH_VARARGS | METH_KWDS` functions. When
// the interpreter tries to use a call_indirect to invoke these methods, we hit
// an indirect call signature mismatch fatal error.
//
// Traditionally we used a JS trampoline to deal with this, because calls from
// JS to Wasm don't care if the wrong number of arguments are passed. However,
// these trampolines do not work with JSPI because we cannot stack switch
// through JavaScript frames.
//
// Originally JSPI implied wasm type reflection, so we could ask JS what the
// type of the function was and then select a `call_indirect` with the right
// number of arguments based on this result.
//
// The new JSPI does not imply that wasm type reflection exists, so we need a
// way to handle the case when JSPI is available but wasm type reflection is
// not. What we do here is make a tiny WebAssembly module that attempts to
// import a single function. If the signature of the function matches the
// signature of the import, it will succeed. Otherwise, we will raise a
// LinkError.
//
// We only need to handle functions with four different possible signatures:
// (n i32's) => i32 where n is between 0 and 3. So we try to link at most 4
// different Wasm modules and find out the signature.

const checkerModules = [undefined, undefined, undefined, undefined];

function makeCheckerModule(n) {
  // Make a webassembly module of the form:
  //
  // (module
  //     (import "e" "f" (func (param i32 ... i32) (result i32)))
  // )
  //
  // with n i32's. We'll try to import the function to this module to see if it
  // has this signature. If not it rasises a link error.
  return new WebAssembly.Module(
    // prettier-ignore
    new Uint8Array([
      0, 97, 115, 109, // magic number
      1,  0,   0,   0, // wasm version
      // Type section code and byte length
      1, 5 + n,
      1, // One type
      // Type is (i32 i32 ... i32) => i32 where there are n i32's
      96, n, ...Array.from({ length: n }, () => 127),
      1, 127,
      // Import section code and byte length
      2, 7,
      // One import
      1,
      // "e" "f"
      1, 101, 1, 102,
      //   A function of type 0
      0, 0,
    ]),
  );
}

function getCheckerModule(n) {
  if (checkerModules[n] === undefined) {
    checkerModules[n] = makeCheckerModule(n);
  }
  return checkerModules[n];
}

export function calculateWasmFuncNargsFallback(functionPtr) {
  for (let n = 0; n < 4; n++) {
    const mod = getCheckerModule(n);
    const imports = {
      e: { f: wasmTable.get(functionPtr) },
    };
    try {
      new WebAssembly.Instance(mod, imports);
      return n;
    } catch (e) {
      // Should be a LinkError, if not we have a logic error. Raise fatal error
      // so it's noisy.
      if (!(e instanceof WebAssembly.LinkError)) {
        throw e;
      }
    }
  }
  return -1;
}
