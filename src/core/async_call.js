mergeInto(LibraryManager.library, {
  hiwire_suspending_call_bound: function () {
    async function f(idfunc, idthis, idargs) {
      let func = Hiwire.get_value(idfunc);
      let this_;
      if (idthis === 0) {
        this_ = null;
      } else {
        this_ = Hiwire.get_value(idthis);
      }
      let args = Hiwire.get_value(idargs);
      let result = await func.apply(this_, args);
      return Hiwire.new_value(result);
    }
    const suspending_f = new WebAssembly.Function(
      { parameters: ["externref", "i32", "i32", "i32"], results: ["i32"] },
      f,
      { suspending: "first" },
    );
    const bytes = [
      0, 97, 115, 109, 1, 0, 0, 0, 1, 16, 2, 96, 4, 111, 127, 127, 127, 1, 127,
      96, 3, 127, 127, 127, 1, 127, 2, 14, 2, 1, 101, 1, 115, 3, 111, 1, 1, 101,
      1, 105, 0, 0, 3, 2, 1, 1, 7, 5, 1, 1, 111, 0, 1, 10, 22, 1, 20, 1, 1, 111,
      35, 0, 34, 3, 32, 0, 32, 1, 32, 2, 16, 0, 32, 3, 36, 0, 11,
    ];
    const module = new WebAssembly.Module(new Uint8Array(bytes));
    const instance = new WebAssembly.Instance(module, {
      e: {
        s: Module.suspenderGlobal,
        i: suspending_f,
      },
    });
    _hiwire_suspending_call_bound = instance.exports.o;
  },
  hiwire_suspending_call_bound__postset: "_hiwire_suspending_call_bound();",
});
