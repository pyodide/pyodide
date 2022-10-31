const API = Module.API;
const Hiwire = {};
const Tests = {};
API.tests = Tests;
API.version = "0.22.0.dev0";
Module.hiwire = Hiwire;
try {
  Module.suspenderGlobal = new WebAssembly.Global(
    { value: "externref", mutable: true },
    null,
  );
} catch (e) {
  // Browser doesn't support externref. This implies it also doesn't support
  // stack switching so we won't need a suspender.
}
