// This is here to suppress import errors from undefined imports. The functions
// are actually defined in jsverror.ts.
addToLibrary({
  Jsv_GetError_import: () => {},
  JsvError_Check: () => {},
  Jsv_GetNoValue_import: () => {},
  JsvNoValue_Check: () => {},
  JSTag: "WebAssembly.JSTag ?? new WebAssembly.Tag({ parameters: ['externref'] })",
});
