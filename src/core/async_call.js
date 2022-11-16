mergeInto(LibraryManager.library, {
  hiwire_syncify: function () {
    throw new Error("Internal error. This should not happen.");
  },
  hiwire_syncify__postset: "Module.initSuspenders();",
});
