const checkerModules = [undefined, undefined, undefined, undefined];

function makeCheckerModule(n) {
  // Make a webassembly module of the form:
  //
  // (module
  //     (import "e" "f" (func (param i32 ... i32) (result i32)))
  // )
  //
  // with n i32's. We'll try to import the function to this module to see if it
  // has this signature.
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
    try {
      new WebAssembly.Instance(getCheckerModule(n), {
        e: { f: wasmTable.get(functionPtr) },
      });
      return n;
    } catch (e) {}
  }
  return -1;
}
