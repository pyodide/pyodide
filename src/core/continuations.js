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
