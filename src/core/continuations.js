// prettier-ignore
const WASM_PRELUDE = [
  0x00, 0x61, 0x73, 0x6d, // magic ("\0asm")
  0x01, 0x00, 0x00, 0x00, // version: 1
];

/**
 * This helper method finishes the section from the section body. It returns
 * [sectionCode, sectionLength, ...sectionBody]
 *
 * See https://webassembly.github.io/spec/core/binary/modules.html#sections
 */
function insertSectionPrefix(sectionCode, sectionBody) {
  var section = [sectionCode];
  uleb128Encode(sectionBody.length, section); // length of section in bytes
  section.push(...sectionBody);
  return section;
}

// See https://webassembly.github.io/spec/core/appendix/index-types.html
const typeCodes = {
  i32: 0x7f,
  i64: 0x7e,
  f32: 0x7d,
  f64: 0x7c,
  externref: 0x6f,
  void: 0x40,
};

// See https://webassembly.github.io/spec/core/appendix/index-instructions.html
const constCodes = {
  i32: 0x41,
  i64: 0x42,
  f32: 0x43,
  f64: 0x44,
};

/**
 * Convert from an emscripten sig to a wasm signature.
 *
 * Emscripten provides us with Emscripten sigs, WebAssembly.Function
 * requires wasm sigs.
 *
 * Emscripten sigs only have vijfd but it's convenient to also include
 * externref.
 *
 * @param {string} sig Emscripten signature
 * @returns wasm signature
 */
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

/**
 * The type section of a generated wasm module.
 *
 * The body of the type section is a vector of function types.
 * See https://webassembly.github.io/spec/core/binary/modules.html#type-section
 */
class TypeSection {
  constructor() {
    this._numTypes = 0;
    this._section = [0];
  }

  /**
   * Adds an emscripten signature to the type section
   * @param {string} sig the Emscripten signature
   * @returns the index of the added type
   */
  addEmscripten(sig) {
    return this.addWasm(emscriptenSigToWasm(sig));
  }

  /**
   * Adds a wasm signature to the type section
   * @param {*} The wasm signature
   * @returns the index of the added type
   */
  addWasm({ parameters, results }) {
    // A function type is 0x60 followed by a vector of value types representing
    // the parameters followed by a vector of value types representing the
    // results. See index of types.
    this._section.push(0x60); // functype code
    // parameters
    uleb128Encode(parameters.length, this._section);
    for (let p of parameters) {
      this._section.push(typeCodes[p]);
    }
    // results
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

// Names are encoded as a vector of bytes:
// https://webassembly.github.io/spec/core/binary/values.html#names
function encodeStr(s) {
  const buf = new TextEncoder().encode(s);
  return [buf.length, ...buf];
}

// The import section is a vector of imports.
// See https://webassembly.github.io/spec/core/binary/modules.html#binary-importsec
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

  /**
   * Add a function import
   * @param {*} name The name of the function import
   * @param {*} sig the index into the type table
   * @returns the index of the function
   */
  addFunction(name, sig) {
    this._addName(name);
    // A function import is specified by the index into the type table
    this._section.push(ImportSection.descr.func, sig);
    this._numImports++;
    return this.numFuncs++;
  }

  /**
   * Add a table. Always a table of funcref.
   * @param {*} name The name of the table import
   */
  addTable(name) {
    this._addName(name);
    this._section.push(
      ImportSection.descr.table,
      0x70 /* type funcref */,
      0 /* no max */,
      0 /* no min */,
    );
    this._numImports++;
  }

  /**
   * Add a global of the given type
   * @param {string} name
   * @param {string} type A value type, so one of i32, i64, f32, f64, or
   * externref
   * @returns The index of the added global
   */
  addGlobal(name, type) {
    this._addName(name);
    // 0x01 = mutable
    this._section.push(ImportSection.descr.global, typeCodes[type], 0x01);
    this._numImports++;
    return this.numGlobals++;
  }

  /**
   * Add an exception handling tag.
   * @param {*} name The name of the import
   * @param {*} sig The signature of the tag. Must have empty parameters, tag
   * sigs can only have results.
   */
  addTag(name, sig) {
    this._addName(name);
    // The 0 is reserved for future use (eg for wasm-stack-switching?)
    // https://webassembly.github.io/exception-handling/core/binary/modules.html#binary-tag
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

/**
 * Generate a code section with one code object. We never need more than one. A
 * code section is a vector of codes. A code entry consists of the size in bytes
 * followed by a vector of locals which is run length encoded then the function
 * body, ending in `end`.
 *
 * https://webassembly.github.io/spec/core/binary/modules.html#code-section
 */
class CodeSection {
  /**
   * Takes a varargs of local variables.
   * A code object
   */
  constructor(...locals) {
    this._section = [];
    this.add(locals.length);
    for (let l of locals) {
      this.add(1, typeCodes[l]);
    }
  }

  /**
   * Use this for any one-off instructions.
   */
  add(...args) {
    this._section.push(...args);
  }

  local_get(idx) {
    this.add(0x20, idx);
  }

  local_set(idx) {
    this.add(0x21, idx);
  }

  local_tee(idx) {
    this.add(0x22, idx);
  }

  global_get(idx) {
    this.add(0x23, idx);
  }

  global_set(idx) {
    this.add(0x24, idx);
  }

  call(func) {
    this.add(0x10, func);
  }

  call_indirect(func) {
    this.add(0x11, func, 0);
  }

  const(type, ...val) {
    this.add(constCodes[type], ...val);
  }

  end() {
    this.add(0x0b);
  }

  generate() {
    this.end();
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
    // Have to record the number of imported functions to know the index of the
    // function we define and want to export
    this._numImportFuncs = imports.numFuncs;
  }

  /**
   * We export exactly one function, so this sets the functionSection to have
   * the given export type.
   * @param {} type
   */
  setExportType(type) {
    const functionSection = [
      0x01, // number of functions = 1
      type, // which has the type we plan to export
    ];
    this.addSectionBody(0x03, functionSection);
    const exportSection = [
      0x01, // One export
      ...encodeStr("o"),
      0x00, // a function
      this._numImportFuncs, // index of the function we define
    ];
    this.addSectionBody(0x07, exportSection);
  }

  generate() {
    const bytes = new Uint8Array(this._sections.flat());
    return new WebAssembly.Module(bytes);
  }
}

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
 * You can look in src/js/test/unit/invokes/ for a few examples of what this
 * function produces.
 *
 * See
 * https://webassembly.github.io/exception-handling/core/appendix/index-instructions.html
 */
function createInvokeModule(sig) {
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

let jsWrapperTag;
try {
  jsWrapperTag = new WebAssembly.Tag({ parameters: ["externref"] });
  Module.jsWrapperTag = jsWrapperTag;
} catch (e) {}

if (jsWrapperTag) {
  Module.wrapException = (e) => new WebAssembly.Exception(jsWrapperTag, [e]);
}

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
Module.createInvoke = createInvoke;

// We patched Emscripten to call this function on the wasmImports just prior to
// wasm instantiation if it is defined. It replaces all invoke functions with
// our Wasm invokes if wasm EH is available.
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
