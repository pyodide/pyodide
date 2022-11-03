const API = Module.API;
const Hiwire = {};
const Tests = {};
API.tests = Tests;
API.version = "0.22.0.dev0";
Module.hiwire = Hiwire;

function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

function patchCheckEmscriptenSignalHelpers() {
  const _orig_Py_CheckEmscriptenSignals_Helper =
    _Py_CheckEmscriptenSignals_Helper;
  const suspending = new WebAssembly.Function(
    { parameters: ["externref"], results: [] },
    () => sleep(0),
    { suspending: "first" },
  );
  const bytes = [
    0, 97, 115, 109, 1, 0, 0, 0, 1, 9, 2, 96, 0, 1, 127, 96, 1, 111, 0, 2, 27,
    4, 1, 101, 1, 115, 3, 111, 1, 1, 101, 1, 99, 3, 127, 1, 1, 101, 1, 105, 0,
    0, 1, 101, 1, 114, 0, 1, 3, 2, 1, 0, 7, 5, 1, 1, 111, 0, 2, 10, 23, 1, 21,
    1, 1, 111, 35, 1, 4, 64, 35, 0, 34, 0, 16, 1, 32, 0, 36, 0, 11, 16, 0, 11,
  ];
  const module = new WebAssembly.Module(new Uint8Array(bytes));
  const instance = new WebAssembly.Instance(module, {
    e: {
      s: Module.suspenderGlobal,
      r: suspending,
      i: _orig_Py_CheckEmscriptenSignals_Helper,
      c: Module.validSuspender,
    },
  });
  _Py_CheckEmscriptenSignals_Helper = instance.exports.o;
}

function patchHiwireSyncify() {
  const suspending_f = new WebAssembly.Function(
    { parameters: ["externref", "i32"], results: ["i32"] },
    async (x) => {
      return Hiwire.new_value(await Hiwire.get_value(x));
    },
    { suspending: "first" },
  );

  const bytes = [
    0, 97, 115, 109, 1, 0, 0, 0, 1, 20, 4, 96, 2, 111, 127, 1, 127, 96, 0, 1,
    111, 96, 1, 111, 0, 96, 1, 127, 1, 127, 2, 54, 5, 1, 101, 1, 115, 3, 111, 1,
    1, 101, 1, 99, 3, 127, 1, 1, 101, 1, 105, 0, 0, 1, 101, 10, 115, 97, 118,
    101, 95, 115, 116, 97, 116, 101, 0, 1, 1, 101, 13, 114, 101, 115, 116, 111,
    114, 101, 95, 115, 116, 97, 116, 101, 0, 2, 3, 2, 1, 3, 7, 5, 1, 1, 111, 0,
    3, 10, 35, 1, 33, 1, 2, 111, 35, 1, 69, 4, 64, 65, 0, 15, 11, 16, 1, 33, 2,
    35, 0, 34, 1, 32, 0, 16, 0, 32, 1, 36, 0, 32, 2, 16, 2, 11,
  ];
  const module = new WebAssembly.Module(new Uint8Array(bytes));
  const instance = new WebAssembly.Instance(module, {
    e: {
      s: Module.suspenderGlobal,
      i: suspending_f,
      c: Module.validSuspender,
      save_state: function () {
        return {
          stackBase: Module.basePointer,
          stackCurrent: Module.___stack_pointer.value,
          stackContents: Module.HEAP8.slice(
            Module.___stack_pointer.value,
            Module.basePointer,
          ),
          pyTState: Module._captureState(),
        };
      },
      restore_state: function (state) {
        Module.basePointer = state.stackBase;
        Module.___stack_pointer.value = state.stackCurrent;
        Module.HEAP8.subarray(state.stackCurrent, state.stackBase).set(
          state.stackContents,
        );
        Module._restoreState(state.pyTState);
      },
    },
  });
  _hiwire_syncify = instance.exports.o;
}

Module.wrapApply = function (apply) {
  const bytes = [
    0, 97, 115, 109, 1, 0, 0, 0, 1, 20, 2, 96, 5, 127, 127, 127, 127, 127, 1,
    127, 96, 6, 111, 127, 127, 127, 127, 127, 1, 127, 2, 14, 2, 1, 101, 1, 115,
    3, 111, 1, 1, 101, 1, 105, 0, 0, 3, 2, 1, 1, 7, 5, 1, 1, 111, 0, 1, 10, 20,
    1, 18, 0, 32, 0, 36, 0, 32, 1, 32, 2, 32, 3, 32, 4, 32, 5, 16, 0, 11,
  ];
  var module = new WebAssembly.Module(new Uint8Array(bytes));
  var instance = new WebAssembly.Instance(module, {
    e: {
      s: Module.suspenderGlobal,
      i: apply,
    },
  });
  return new WebAssembly.Function(
    { parameters: ["i32", "i32", "i32", "i32", "i32"], results: ["externref"] },
    instance.exports.o,
    { promising: "first" },
  );
};

Module.initSuspenders = function () {
  try {
    // Feature detect externref. Also need it for wrapApply to work.
    Module.suspenderGlobal = new WebAssembly.Global(
      { value: "externref", mutable: true },
      null,
    );
    // Feature detect WebAssembly.Function and JS Promise integration
    Module.wrapApply(
      new WebAssembly.Function(
        { parameters: ["i32", "i32", "i32", "i32", "i32"], results: ["i32"] },
        () => {},
      ),
    );
  } catch (e) {
    // Browser doesn't support externref. This implies it also doesn't support
    // stack switching so we won't need a suspender.
    Module.validSuspender = { value: 0 };
    Module.suspendersAvailable = false;
    return;
  }
  Module.validSuspender = new WebAssembly.Global(
    { value: "i32", mutable: true },
    0,
  );
  // patchCheckEmscriptenSignalHelpers();
  patchHiwireSyncify();
  Module.suspendersAvailable = true;
};
