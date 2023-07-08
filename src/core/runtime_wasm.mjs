/**
 * Tools to generate webassembly adaptor modules at runtime.
 *
 * This is not intended to be fully general but rather to balance tradeoff
 * between expressiveness and simplicity. I find that the hardest part of
 * maintaining hand-written modules is updating indices and offsets when
 * changing the wasm code. Thus, this makes it so that it is not necessary to
 * manually update lengths or indices.
 *
 * The generated modules have five sections: Type, Imports, Exports, Function,
 * and Code. The following limitations allow minor code simplifications. In the
 * future they could be relaxed if needed for some reason.
 *
 * Restrictions on Imports:
 *  * global imports are mutable
 *  * no memory import
 *  * table imports are unbounded tables of funcrefs.
 *
 * Restrictions on Functions:
 *  * exactly one
 *
 * Restrictions on Exports:
 *  * exactly one export
 *  * which is the function we define
 *  * called "o"
 *
 * Restriction on Code:
 *  * can't run length encode exports
 */

// prettier-ignore
export const WASM_PRELUDE = [
  0x00, 0x61, 0x73, 0x6d, // magic ("\0asm")
  0x01, 0x00, 0x00, 0x00, // version: 1
];

/**
 * This helper method finishes the section from the section body. It returns
 * [sectionCode, sectionLength, ...sectionBody]
 *
 * See https://webassembly.github.io/spec/core/binary/modules.html#sections
 */
export function insertSectionPrefix(sectionCode, sectionBody) {
  var section = [sectionCode];
  uleb128Encode(sectionBody.length, section); // length of section in bytes
  section.push(...sectionBody);
  return section;
}

// See https://webassembly.github.io/spec/core/appendix/index-types.html
export const typeCodes = {
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
export function emscriptenSigToWasm(sig) {
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
export class TypeSection {
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
export class ImportSection {
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
   * Add a global of the given type. All globals are mutable.
   *
   * @param {string} name
   * @param {string} type A value type, so one of i32, i64, f32, f64, or
   * externref
   * @returns The index of the added global
   */
  addGlobal(name, type) {
    this._addName(name);
    this._section.push(
      ImportSection.descr.global,
      typeCodes[type],
      0x01 /* mutable */,
    );
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
export class CodeSection {
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

export class WasmModule {
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
