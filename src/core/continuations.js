/**
 * This file handles stack switching for the C in-memory stack and for the
 * inaccessible wasm stack.
 */

/**
 * This file is processed with build_continuations.mjs and then #included into
 * continuations.c as the definition of continuations_init_js
 *
 * build_continuations resolves the wat imports by assembling wat and wraps it
 * in EM_JS.
 */
import wrap_syncifying_wasm from "./wrap_syncifying.wat";


// prettier-ignore
const WASM_PRELUDE = [
  0x00, 0x61, 0x73, 0x6d, // magic ("\0asm")
  0x01, 0x00, 0x00, 0x00, // version: 1
];

function insertSectionPrefix(sectionCode, sectionBody) {
  var section = [sectionCode];
  uleb128Encode(sectionBody.length, section); // length of section in bytes
  section.push(...sectionBody);
  return section;
}

const typeCodes = {
  i32: 0x7f,
  i64: 0x7e,
  f32: 0x7d,
  f64: 0x7c,
  externref: 0x6f,
};

const constCodes = {
  i32: 0x41,
  i64: 0x42,
  f32: 0x43,
  f64: 0x44,
};

function emscriptenSigToWasm(sig) {
  const lookup = {
    i: "i32",
    j: "i64",
    f: "f32",
    d: "f64",
    e: "externref",
    v: "",
  };
  const parameters = sig.split("").map((x) => lookup[x]);
  const result = parameters.shift();
  const results = result ? [result] : [];
  return { parameters, results };
}

class TypeSection {
  constructor() {
    this._numTypes = 0;
    this._section = [0];
  }

  addEmscripten(sig) {
    return this.addWasm(emscriptenSigToWasm(sig));
  }

  addWasm({ parameters, results }) {
    this._section.push(0x60 /* form: func */);
    uleb128Encode(parameters.length, this._section);
    for (let p of parameters) {
      this._section.push(typeCodes[p]);
    }
    uleb128Encode(results.length, this._section);
    for (let p of results) {
      this._section.push(typeCodes[p]);
    }
    return this._numTypes++;
  }

  generate() {
    this._section[0] = this._numTypes;
    return insertSectionPrefix(0x01, this._section);
  }
}

function encodeStr(s) {
  const buf = new TextEncoder().encode(s);
  return [buf.length, ...buf];
}

class ImportSection {
  constructor() {
    this._numImports = 0;
    this.numGlobals = 0;
    this.numFuncs = 0;
    this._section = [0];
  }

  _addName(name) {
    this._section.push(...ImportSection._module);
    this._section.push(...encodeStr(name));
  }

  addFunction(name, sig) {
    this._addName(name);
    this._section.push(ImportSection.descr.func, sig);
    this._numImports++;
    return this.numFuncs++;
  }

  addTable(name) {
    this._addName(name);
    this._section.push(ImportSection.descr.table, 0x70, 0, 0);
    this._numImports++;
  }

  addGlobal(name, type) {
    this._addName(name);
    // 0x01 = mutable
    this._section.push(ImportSection.descr.global, typeCodes[type], 0x01);
    this._numImports++;
    return this.numGlobals++;
  }

  addTag(name, sig) {
    this._addName(name);
    this._section.push(ImportSection.descr.tag, 0, sig);
    this._numImports++;
  }

  generate() {
    this._section[0] = this._numImports;
    return insertSectionPrefix(0x02, this._section);
  }
}
ImportSection._module = encodeStr("e");
ImportSection.descr = {
  func: 0,
  table: 1,
  mem: 2,
  global: 3,
  tag: 4,
};

class CodeSection {
  constructor(...locals) {
    this._section = [];
    this._section.push(locals.length);
    for (let l of locals) {
      this._section.push(1, typeCodes[l]);
    }
  }

  add(...args) {
    this._section.push(...args);
  }

  local_get(idx) {
    this._section.push(0x20, idx);
  }

  local_set(idx) {
    this._section.push(0x21, idx);
  }

  local_tee(idx) {
    this._section.push(0x22, idx);
  }

  global_get(idx) {
    this._section.push(0x23, idx);
  }

  global_set(idx) {
    this._section.push(0x24, idx);
  }

  call(func) {
    this._section.push(0x10, func);
  }

  call_indirect(func) {
    this._section.push(0x11, func, 0);
  }

  const(type, ...val) {
    this._section.push(constCodes[type], ...val);
  }

  end() {
    this._section.push(0x0b);
  }

  generate() {
    return insertSectionPrefix(0x0a, insertSectionPrefix(1, this._section));
  }
}

class WasmModule {
  constructor() {
    this._sections = [WASM_PRELUDE];
  }

  addSection(section) {
    this._sections.push(section.generate());
  }

  addSectionBody(sectionCode, sectionBody) {
    this._sections.push(insertSectionPrefix(sectionCode, sectionBody));
  }

  addImportSection(imports) {
    this.addSection(imports);
    this._numImportFuncs = imports.numFuncs;
  }

  setExportType(type) {
    const functionSection = [
      0x01, // number of functions = 1
      type,
    ];
    this.addSectionBody(0x03, functionSection);
    const exportSection = [
      0x01, // One export
      ...encodeStr("o"),
      0x00, // a function
      this._numImportFuncs,
    ];
    this.addSectionBody(0x07, exportSection);
  }

  generate() {
    const bytes = new Uint8Array(this._sections.flat());
    // const fs = require("fs");
    // fs.writeFileSync("gen.wasm", bytes);
    return new WebAssembly.Module(bytes);
  }
}

function createInvokeModule(sig) {
  const mod = new WasmModule();
  const types = new TypeSection();
  const invoke_sig = emscriptenSigToWasm(sig);
  const export_sig = structuredClone(invoke_sig);
  export_sig.parameters.unshift("i32");
  const try_sig = structuredClone(invoke_sig);
  try_sig.parameters = [];
  const invoke_tidx = types.addWasm(invoke_sig);
  const export_tidx = types.addWasm(export_sig);
  const try_tidx = types.addWasm(try_sig);
  const tag_tidx = types.addEmscripten("ve");
  const save_tidx = types.addEmscripten("i");
  const restore_tidx = types.addEmscripten("vi");
  const setThrew_tidx = types.addEmscripten("vii");
  mod.addSection(types);

  const imports = new ImportSection();
  imports.addTable("t");
  imports.addTag("tag", tag_tidx);
  const save_func = imports.addFunction("s", save_tidx);
  const restore_func = imports.addFunction("r", restore_tidx);
  const set_threw_func = imports.addFunction("q", setThrew_tidx);
  mod.addImportSection(imports);
  mod.setExportType(export_tidx);

  const code = new CodeSection(["i32"]);
  const stateLocal = export_sig.parameters.length;

  code.call(save_func);
  code.local_set(stateLocal);

  code.add(0x06, try_tidx); // try
  for (let i = 1; i < export_sig.parameters.length; i++) {
    code.local_get(i);
  }
  code.local_get(0);

  code.call_indirect(invoke_tidx);
  code.add(0x07, 0); // catch $tag
  code.add(0x1a); // drop the caught externref
  code.local_get(stateLocal);
  code.call(restore_func);

  code.const("i32", 0x01);
  code.const("i32", 0x00);
  code.call(set_threw_func);
  const sizes = {
    i32: 1,
    i64: 1,
    f32: 4,
    f64: 8,
  };
  for (let x of export_sig.results) {
    code.const(x, ...Array(sizes[x]).fill(0));
  }
  code.end(); // end try
  code.end(); // end func def
  mod.addSection(code);

  return mod.generate();
}

let jsWrapperTag;
try {
  jsWrapperTag = new WebAssembly.Tag({ parameters: ["externref"] });
  Module.jsWrapperTag = jsWrapperTag;
} catch (e) {}

if (jsWrapperTag) {
  Module.wrapException = (e) => new WebAssembly.Exception(jsWrapperTag, [e]);
}

function createInvoke(sig) {
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
Module.createInvoke = createInvoke;

Module.adjustWasmImports = function (wasmImports) {
  if (jsWrapperTag) {
    const i = "invoke_";
    for (let name of Object.keys(wasmImports)) {
      if (!name.startsWith(i)) {
        continue;
      }
      wasmImports[name] = createInvoke(name.slice(i.length));
    }
  }
};

/**
 * Module.syncifyHandler does all of the work of hiwire_syncify (defined in
 * hiwire).
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
        // Error handling is tricky here. We want to set the error flag after
        // unswitching the stack. Just store the error for the moment.
        Module.syncify_error = e;
      }
    },
    { suspending: "first" },
  );
  // This module checks validSuspender, if there is no validSuspender returns 0
  // for error. Otherwise, it calls save_state, stores the result into an
  // externef, calls suspending_f with suspenderGlobal and the original argument
  // then it calls restore_state with the saved state and returns the result.
  // See wrap_syncifying.wat
  const module = new WebAssembly.Module(new Uint8Array(wrap_syncifying_wasm));
  const instance = new WebAssembly.Instance(module, {
    e: {
      s: Module.suspenderGlobal,
      i: suspending_f,
      c: Module.validSuspender,
      save: save_state,
      restore: restore_state,
    },
  });
  HEAP32[_syncifyHandler / 4] = addFunction(instance.exports.o);
}

Module.suspendableApply = function (...args) {
  // validSuspender is a flag so that we can ask for permission before trying
  // to suspend. We can't ask for forgiveness because our normal technique for
  // this is to insert a JavaScript frame where we can catch the error
  // generated. We cannot suspend through JavaScript frames (this limitation
  // is part of the intentional design of Wasm Promise Integration).
  Module.validSuspender.value = true;
  // Record the current stack position. See StackState in continuations.js
  Module.stackStop = Module.___stack_pointer.value;
  return Module.suspendableApplyHandler(...args);
};

// for using wasm types as map keys
function wasmTypeToString(ty) {
  return `params:${ty.parameters};results:${ty.results}`;
}

const selectorModuleMap = new Map();
function createSelectorModule(async_type) {
  const async_type_str = wasmTypeToString(async_type);
  if (selectorModuleMap.has(async_type_str)) {
    return selectorModuleMap.get(async_type_str);
  }
  const mod = new WasmModule();
  const sync_type = structuredClone(async_type);
  sync_type.parameters.shift();
  const ts = new TypeSection();
  const async_tidx = ts.addWasm(async_type);
  const sync_tidx = ts.addWasm(sync_type);
  mod.addSection(ts);

  const imports = new ImportSection();

  const suspenderCheck = imports.addGlobal("c", "i32");
  const suspenderGlobal = imports.addGlobal("s", "externref");
  const sync_fn = imports.addFunction("f", sync_tidx);
  const async_fn = imports.addFunction("a", async_tidx);
  mod.addImportSection(imports);
  mod.setExportType(sync_tidx);

  const code = new CodeSection("externref");
  const suspenderLocal = sync_type.parameters.length;
  code.global_get(suspenderCheck);
  code.add(0x45); // i32.eqz
  code.add(0x04, 0x40); // if
  for (let i = 0; i < sync_type.parameters.length; i++) {
    code.local_get(i);
  }
  code.call(sync_fn);
  code.add(0x0f); // return
  code.end(); // end if

  code.global_get(suspenderGlobal);
  code.local_tee(suspenderLocal);
  for (let i = 0; i < sync_type.parameters.length; i++) {
    code.local_get(i);
  }
  code.call(async_fn);
  code.local_get(suspenderLocal);
  code.global_set(suspenderGlobal);
  code.end();
  mod.addSection(code);
  const module = mod.generate();
  selectorModuleMap.set(async_type_str, module);
  return module;
}

function createSelector(sync_fn, async_wrapper) {
  const async_type = WebAssembly.Function.type(async_wrapper);
  const module = createSelectorModule(async_type);
  const instance = new WebAssembly.Instance(module, {
    e: {
      a: async_wrapper,
      f: sync_fn,
      s: Module.suspenderGlobal,
      c: Module.validSuspender,
    },
  });
  return instance.exports["o"];
}
Module.createSelector = createSelector;

const promisingModuleMap = new Map();
function getPromisingModule(orig_type) {
  const type_str = wasmTypeToString(orig_type);
  if (promisingModuleMap.has(type_str)) {
    return promisingModuleMap.get(type_str);
  }
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
  code.end();
  mod.addSection(code);
  const module = mod.generate();
  promisingModuleMap.set(type_str, module);
  return module;
}

const promisingFunctionMap = new WeakMap();
function createPromising(wasm_func) {
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
Module.createPromising = createPromising;

function syncHandler(genfunc, ...args) {
  let gen = genfunc(...args);
  let [fptr, call_args] = gen.next().value;
  return gen.next(getWasmTableEntry(fptr)(...call_args)).value;
}

async function promisingHandler(genfunc, ...args) {
  let gen = genfunc(...args);
  let [fptr, call_args] = gen.next().value;
  return gen.next(await createPromising(getWasmTableEntry(fptr))(...call_args))
    .value;
}

function getHandlerFn(trampoline, sig) {
  const sync_fn = syncHandler.bind(null, trampoline);
  if (Module.suspendersAvailable) {
    const wasmsig = emscriptenSigToWasm(sig);
    wasmsig.parameters.unshift("externref");
    const async_wrapper = new WebAssembly.Function(
      wasmsig,
      promisingHandler.bind(null, trampoline),
      { suspending: "first" },
    );
    return createSelector(sync_fn, async_wrapper);
  } else {
    return convertJsFunctionToWasm(sync_fn, sig);
  }
}
Module.getHandlerFn = getHandlerFn;

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
function initSuspenders() {
  try {
    Module.suspenderGlobal = new WebAssembly.Global(
      { value: "externref", mutable: true },
      null,
    );
    Module.suspendableApplyHandler = createPromising(Module.asm._pyproxy_apply);
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
    Module.syncifyHandler = function () {
      Module.handle_js_error(Error("Syncify not supported"));
      return 0;
    };
  }
}
