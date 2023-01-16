const API = Module.API;
const Hiwire = {};
const Tests = {};
API.tests = Tests;
API.version = "0.22.0";
Module.hiwire = Hiwire;
const getTypeTag = (x) => Object.prototype.toString.call(x);
API.getTypeTag = getTypeTag;

if (typeof document !== "undefined") {
  // Emscripten SDL libraries relies on Module.canvas
  Module.canvas = document.querySelector("canvas#canvas");
}
