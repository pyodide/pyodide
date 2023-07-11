import wrap_syncifying_wasm from "./wrap_syncifying.wat";
import {
  WasmModule,
  CodeSection,
  ImportSection,
  TypeSection,
} from "./runtime_wasm.mjs";

/**
 * Set the syncifyHandler used by hiwire_syncify.
 *
 * syncifyHandler does the work of hiwire_syncify (defined in hiwire).
 */
function setSyncifyHandler() {
  const suspending_f = new WebAssembly.Function(
    { parameters: ["externref", "i32"], results: ["i32"] },
    async (x) => {
      try {
        return Hiwire.new_value(await Hiwire.get_value(x));
      } catch (e) {
        if (e && e.pyodide_fatal_error) {
          throw e;
        }
        // Error handling is tricky here. We need to wait until after
        // unswitching the stack to set the Python error flag. Just store the
        // error for the moment. We move this into the error flag in
        // hiwire_syncify_handle_error in hiwire.c
        Module.syncify_error = e;
      }
    },
    { suspending: "first" },
  );
  // See wrap_syncifying.wat.
  const module = new WebAssembly.Module(new Uint8Array(wrap_syncifying_wasm));
  const instance = new WebAssembly.Instance(module, {
    e: {
      s: Module.suspenderGlobal,
      i: suspending_f,
      c: Module.validSuspender,
    },
  });
  // Assign to the function pointer so that hiwire_syncify calls our wrapper
  // function
  HEAP32[_syncifyHandler / 4] = addFunction(instance.exports.o);
}

export function promisingApply(...args) {
  // validSuspender is a flag so that we can ask for permission before trying to
  // suspend.
  Module.validSuspender.value = true;
  // Record the current stack position.
  Module.stackStop = Module.___stack_pointer.value;
  return Module.promisingApplyHandler(...args);
}

// for using wasm types as map keys
function wasmTypeToString(ty) {
  return `params:${ty.parameters};results:${ty.results}`;
}

/**
 * This function stores the first argument into suspenderGlobal and then makes
 * an onward call with one fewer argument.
 *
 * You can look at src/js/test/unit/wat/promising_<sig>.wat for a few examples
 * of what this function produces.
 */
export function createPromisingModule(orig_type) {
  const mod = new WasmModule();
  const ts = new TypeSection();
  const wrapped_type = structuredClone(orig_type);
  wrapped_type.parameters.unshift("externref");
  const orig_sig = ts.addWasm(orig_type);
  const wrapped_sig = ts.addWasm(wrapped_type);
  mod.addSection(ts);

  const imports = new ImportSection();
  imports.addGlobal("s", "externref");
  const orig = imports.addFunction("i", orig_sig);
  mod.addImportSection(imports);
  mod.setExportType(wrapped_sig);

  const code = new CodeSection();
  code.local_get(0);
  code.global_set(0);
  for (let i = 1; i < wrapped_type.parameters.length; i++) {
    code.local_get(i);
  }
  code.call(orig);
  mod.addSection(code);
  return mod.generate();
}

const promisingModuleMap = new Map();
function getPromisingModule(orig_type) {
  const type_str = wasmTypeToString(orig_type);
  if (promisingModuleMap.has(type_str)) {
    return promisingModuleMap.get(type_str);
  }
  const module = createPromisingModule(orig_type);
  promisingModuleMap.set(type_str, module);
  return module;
}

const promisingFunctionMap = new WeakMap();
/**
 * This creates a wrapper around wasm_func that receives an extra suspender
 * argument and returns a promise. The suspender is stored into suspenderGlobal
 * so it can be used by syncify (see wrap_syncifying.wat)
 *
 * For unit testing, allow passing suspenderGlobal as an argument.
 */
export function createPromising(wasm_func, suspenderGlobal) {
  if (!suspenderGlobal) {
    suspenderGlobal = Module.suspenderGlobal;
  }
  if (promisingFunctionMap.has(wasm_func)) {
    return promisingFunctionMap.get(wasm_func);
  }
  const type = WebAssembly.Function.type(wasm_func);
  const module = getPromisingModule(type);
  const instance = new WebAssembly.Instance(module, {
    e: { i: wasm_func, s: suspenderGlobal },
  });
  const result = new WebAssembly.Function(
    { parameters: type.parameters, results: ["externref"] },
    instance.exports.o,
    { promising: "first" },
  );
  promisingFunctionMap.set(wasm_func, result);
  return result;
}

/**
 * This sets up syncify to work.
 *
 * We need to make:
 *
 * - suspenderGlobal where we store the suspender object
 *
 * - promisingApplyHandler which calls a Python function with stack switching
 *   enabled (used in callPyObjectKwargsSuspending in pyproxy.ts)
 *
 * - the syncifyHandler which uses suspenderGlobal to suspend execution, then
 *   awaits a promise, then resumes execution and returns the promise result
 *   (used by hiwire_syncify)
 *
 * If the creation of these fails because JSPI is missing, then we set it up so
 * that callKwargsSyncifying and hiwire_syncify will always raise errors and
 * everything else can work as normal.
 */
export function initSuspenders() {
  // It would be nice to have a better way to feature detect wasm stack
  // switching than this. For now I haven't come up with anything better.
  // Since createPromising is called in this catch-all block, we unit test it
  // in stack_switching.test.mjs. There is also integration test coverage for
  // it in test_syncify.test_cpp_exceptions_and_syncify.
  try {
    Module.suspenderGlobal = new WebAssembly.Global(
      { value: "externref", mutable: true },
      null,
    );
    Module.promisingApplyHandler = createPromising(Module.asm._pyproxy_apply);
  } catch (e) {}

  Module.jspiSupported = !!Module.promisingApplyHandler;

  if (Module.jspiSupported) {
    Module.validSuspender = new WebAssembly.Global(
      { value: "i32", mutable: true },
      0,
    );
    setSyncifyHandler();
  } else {
    // Browser doesn't support JSPI.
    Module.validSuspender = { value: 0 };
  }
}
