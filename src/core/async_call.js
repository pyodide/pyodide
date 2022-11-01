mergeInto(LibraryManager.library, {
  temp: function () {
    if (typeof WebAssembly.Function === "undefined") {
      return;
    }
    function sleep(ms) {
      return new Promise((res) => setTimeout(res, ms));
    }
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
  },
  temp__postset: "_temp();",
  hiwire_syncify__deps: ["temp"],
  hiwire_syncify: function () {
    const suspending_f = new WebAssembly.Function(
      { parameters: ["externref", "i32"], results: ["i32"] },
      async (x) => {
        return Hiwire.new_value(await Hiwire.get_value(x));
      },
      { suspending: "first" },
    );

    const bytes = [
      0, 97, 115, 109, 1, 0, 0, 0, 1, 12, 2, 96, 2, 111, 127, 1, 127, 96, 1,
      127, 1, 127, 2, 21, 3, 1, 101, 1, 115, 3, 111, 1, 1, 101, 1, 99, 3, 127,
      1, 1, 101, 1, 105, 0, 0, 3, 2, 1, 1, 7, 5, 1, 1, 111, 0, 1, 10, 27, 1, 25,
      1, 1, 111, 35, 1, 69, 4, 64, 65, 0, 15, 11, 35, 0, 34, 1, 32, 0, 16, 0,
      32, 1, 36, 0, 11,
    ];
    const module = new WebAssembly.Module(new Uint8Array(bytes));
    const instance = new WebAssembly.Instance(module, {
      e: {
        s: Module.suspenderGlobal,
        i: suspending_f,
        c: Module.validSuspender,
      },
    });
    _hiwire_syncify = instance.exports.o;
  },
  hiwire_syncify__postset: "_hiwire_syncify();",
});
