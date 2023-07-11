/**
 * Create wasm invokes
 *
 * The "invoke_<sig>" trampolines are used to call functions in C++ try blocks /
 * C contexts where a longjmp can happen. They catch any errors.
 *
 * Ordinarily, Emscripten generates these as JavaScript functions but we need to
 * replace them with wasm functions when possible to enable us to use JS Promise
 * Integration, since JSPI is incompatible with JS trampolines by design.
 *
 * TODO: switching to using wasm error handling will let us get rid of this
 * code. Currently, switching to wasm eh is blocked on Rust support.
 */

import {
  WasmModule,
  CodeSection,
  ImportSection,
  emscriptenSigToWasm,
  TypeSection,
  typeCodes,
} from "./runtime_wasm.mjs";

/**
 * These produce the following pseudocode:
 * ```
 * function (func, ...args) {
 *    let stack = stackSave();
 *    try {
 *       return func(...args);
 *    } catch(e) {
 *      stackRestore(stack);
 *      __setThrew(1, 0);
 *      return 0;
 *    }
 * }
 * ```
 *
 * You can look at src/js/test/unit/wat/invoke_<sig>.wat for a few examples of what this
 * function produces.
 *
 * See
 * https://webassembly.github.io/exception-handling/core/appendix/index-instructions.html
 */
export function createInvokeModule(sig) {
  const mod = new WasmModule();
  const types = new TypeSection();
  // invoke_sig is the signature of the function pointer we have to call
  const invoke_sig = emscriptenSigToWasm(sig);
  // export_sig is the signature of the function we define.
  // It takes one extra function pointer argument
  const export_sig = structuredClone(invoke_sig);
  export_sig.parameters.unshift("i32");
  const invoke_tidx = types.addWasm(invoke_sig);
  const export_tidx = types.addWasm(export_sig);
  // Since results length is <= 1, we can fold the result type. wabt will
  // automatically apply this folding so it's hard to make a unit test if we
  // don't do it. Per the spec:
  //
  //    A block type is given either as a type index that refers to a suitable
  //    function type, or as an optional value type inline, which is a shorthand
  //    for the function type [] -> [valtype?]
  //
  // See https://webassembly.github.io/exception-handling/core/syntax/instructions.html#syntax-blocktype
  const try_tidx = typeCodes[invoke_sig.results[0] || "void"];

  // The tag has an externref which wraps the original exception. We don't
  // actually use the wrapped externref unless the exception isn't caught.
  // Before throwing, Emscripten stores the exception into Module.lastException
  // and it looks there to get info about the exception if it needs it. But if
  // the error goes uncaught, we'll extract the original value of it in
  // src/core/error_handling.ts in convertCppException.
  const tag_tidx = types.addEmscripten("ve");
  const save_tidx = types.addEmscripten("i");
  const restore_tidx = types.addEmscripten("vi");
  const setThrew_tidx = types.addEmscripten("vii");
  mod.addSection(types);

  const imports = new ImportSection();
  imports.addTable("t");
  imports.addTag("tag", tag_tidx);
  const save_stack_func = imports.addFunction("s", save_tidx);
  const restore_stack_func = imports.addFunction("r", restore_tidx);
  const set_threw_func = imports.addFunction("q", setThrew_tidx);
  mod.addImportSection(imports);
  mod.setExportType(export_tidx);

  // We need an extra local to store the stack pointer
  const code = new CodeSection(["i32"]);
  const stackLocal = export_sig.parameters.length;

  // Save the stack into stackLocal
  code.call(save_stack_func);
  code.local_set(stackLocal);

  // try with the same return type as the function we're defining
  code.add(0x06, try_tidx);
  // add the arguments
  for (let i = 1; i < export_sig.parameters.length; i++) {
    code.local_get(i);
  }
  // Then add the function pointer last
  code.local_get(0);
  // make onwards call, if it throws we'll catch it!
  code.call_indirect(invoke_tidx);

  code.add(0x07, 0); // catch $tag
  code.add(0x1a); // drop the caught externref
  // restore stack
  code.local_get(stackLocal);
  code.call(restore_stack_func);

  // call set_threw
  code.const("i32", 0x01);
  code.const("i32", 0x00);
  code.call(set_threw_func);

  // If there's a return value, we need to put some 0's in to return.
  // Since we called set_threw, the caller will ignore the return value
  const sizes = {
    i32: 1,
    i64: 1,
    f32: 4,
    f64: 8,
  };
  for (let x of export_sig.results) {
    code.const(x, ...Array(sizes[x]).fill(0));
  }
  code.end(); // end try block
  mod.addSection(code);

  return mod.generate();
}

export let jsWrapperTag;
try {
  jsWrapperTag = new WebAssembly.Tag({ parameters: ["externref"] });
} catch (e) {}

export const wrapException = (e) =>
  new WebAssembly.Exception(jsWrapperTag, [e]);

function createInvoke(sig) {
  if (!jsWrapperTag) {
    return createInvokeFunction(sig);
  }
  const module = createInvokeModule(sig);
  const instance = new WebAssembly.Instance(module, {
    e: {
      t: wasmTable,
      s: () => stackSave(),
      r: (x) => stackRestore(x),
      q: (x, y) => _setThrew(x, y),
      tag: jsWrapperTag,
    },
  });
  return instance.exports["o"];
}

// We patched Emscripten to call this function on the wasmImports just prior to
// wasm instantiation if it is defined. It replaces all invoke functions with
// our Wasm invokes if wasm EH is available.
export function adjustWasmImports(wasmImports) {
  const i = "invoke_";
  for (let name of Object.keys(wasmImports)) {
    if (!name.startsWith(i)) {
      continue;
    }
    wasmImports[name] = createInvoke(name.slice(i.length));
  }
}
