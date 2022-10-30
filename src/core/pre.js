const API = Module.API;
const Hiwire = {};
const Tests = {};
API.tests = Tests;
API.version = "0.22.0.dev0";
Module.hiwire = Hiwire;
if (typeof WebAssembly.Suspender !== "undefined") {
  Module.newSuspender = function () {
    return new WebAssembly.Suspender();
  };
} else {
  Module.newSuspender = function () {
    return {
      suspendOnReturnedPromise: (x) => x,
      returnPromiseOnSuspend: (x) => x,
    };
  };
}
// Module.suspenders = [[Module.newSuspender(), false]];
Module.suspender = Module.newSuspender();
