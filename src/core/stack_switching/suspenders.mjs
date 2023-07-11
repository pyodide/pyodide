import wrap_syncifying_wasm from "./wrap_syncifying.wat";
import {
  WasmModule,
  CodeSection,
  ImportSection,
  TypeSection,
} from "./runtime_wasm.mjs";

/**
 * syncifyHandler does all of the work of hiwire_syncify (defined in hiwire).
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
 * This function stores the first argument into
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
export function createPromising(wasm_func) {
  if (promisingFunctionMap.has(wasm_func)) {
    return promisingFunctionMap.get(wasm_func);
  }
  const type = WebAssembly.Function.type(wasm_func);
  const module = getPromisingModule(type);
  const instance = new WebAssembly.Instance(module, {
    e: { i: wasm_func, s: Module.suspenderGlobal },
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
 * - applyHandler which creates a suspender and stores it into suspenderGlobal
 *   then makes an onward call (used by callKwargsSyncifying)
 *
 * - the syncifyHandler which uses suspenderGlobal to suspend execution, then
 *   awaits a promise, then resumes execution and returns the promise result
 *   (used by hiwire_syncify)
 *
 * If the creation of these fails because JSPI is missing, then we set it up so
 * that callKwargsSyncifying and hiwire_syncify will always raise errors and
 * everything else can work as normal. In the short term, we'll almost always
 * end
 */
export function initSuspenders() {
  try {
    Module.suspenderGlobal = new WebAssembly.Global(
      { value: "externref", mutable: true },
      null,
    );
    Module.promisingApplyHandler = createPromising(Module.asm._pyproxy_apply);
    Module.suspendersAvailable = true;
  } catch (e) {
    Module.suspendersAvailable = false;
  }
  if (Module.suspendersAvailable) {
    Module.validSuspender = new WebAssembly.Global(
      { value: "i32", mutable: true },
      0,
    );
    setSyncifyHandler();
  } else {
    // Browser doesn't support JSPI.
    Module.validSuspender = { value: 0 };
    Module.suspendersAvailable = false;
  }
}
