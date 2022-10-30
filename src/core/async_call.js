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
    const wrapped_f = new WebAssembly.Function(
      { parameters: ["i32", "i32", "i32"], results: ["externref"] },
      f,
    );
    _hiwire_suspending_call_bound =
      Module.suspender.suspendOnReturnedPromise(wrapped_f);
  },
  hiwire_suspending_call_bound__postset: "_hiwire_suspending_call_bound();",
});
