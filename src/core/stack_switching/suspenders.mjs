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
    { parameters: ["externref", "externref"], results: ["externref"] },
    async (x) => {
      try {
        return nullToUndefined(await x);
      } catch (e) {
        if (e && e.pyodide_fatal_error) {
          throw e;
        }
        // Error handling is tricky here. We need to wait until after
        // unswitching the stack to set the Python error flag. Just store the
        // error for the moment. We move this into the error flag in
        // JsvPromise_Syncify_HandleError in jslib.c
        Module.syncify_error = e;
        return null;
      }
    },
    { suspending: "first" },
  );
  // See wrap_syncifying.wat.
  const module = new WebAssembly.Module(new Uint8Array(wrap_syncifying_wasm));
  const instance = new WebAssembly.Instance(module, {
    e: {
      s: suspenderGlobal,
      i: suspending_f,
      c: validSuspender,
    },
  });
  // Assign to the function pointer so that JsvPromise_syncify calls our wrapper
  // function
  HEAP32[_syncifyHandler / 4] = addFunction(instance.exports.o);
}

let promisingApplyHandler;
export function promisingApply(...args) {
  // validSuspender is a flag so that we can ask for permission before trying to
  // suspend.
  validSuspender.value = true;
  return promisingApplyHandler(...args);
}

// for using wasm types as map keys
function wasmTypeToString(ty) {
  return `params:${ty.parameters};results:${ty.results}`;
}

/**
 * This function stores the first argument into suspenderGlobal and then makes
 * an onward call with one fewer argument. The suspenderGlobal is later used by
 * syncify (see wrap_syncifying.wat)
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
 */
export function createPromising(wasm_func) {
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

export let suspenderGlobal;
try {
  suspenderGlobal = new WebAssembly.Global(
    { value: "externref", mutable: true },
    null,
  );
} catch (e) {
  // An error is thrown if externref isn't supported. In this case JSPI is also
  // not supported and everything is fine.
}

let validSuspender;

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
  // This is what wasm-feature-detect uses to feature detect JSPI. It is not
  // 100% clear based on the text of the JSPI proposal that this will actually
  // work in the future, but if it breaks we can replace it with something else
  // that does work.
  Module.jspiSupported = "Suspender" in WebAssembly;

  if (Module.jspiSupported) {
    validSuspender = new WebAssembly.Global({ value: "i32", mutable: true }, 0);
    promisingApplyHandler = createPromising(wasmExports._pyproxy_apply);
    Module.validSuspender = validSuspender;
    setSyncifyHandler();
  } else {
    // Browser doesn't support JSPI.
    Module.validSuspender = { value: 0 };
  }
}
