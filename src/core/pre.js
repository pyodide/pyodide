const API = Module.API;
const Hiwire = {};
const Tests = {};
let setImmediate = globalThis.setImmediate;
let clearImmediate = globalThis.clearImmediate;
let baseName, fpcGOT, dyncallGOT, fpVal, dcVal;
