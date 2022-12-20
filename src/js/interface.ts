declare var API: any;
declare var Module: any;
/**
 * @private
 */
API.makePublicAPI = function (): PyodideInterface {
  FS = Module.FS;
  PATH = Module.PATH;
  ERRNO_CODES = Module.ERRNO_CODES;
  let namespace = {
    globals,
    FS,
    PATH,
    ERRNO_CODES,
    pyodide_py,
    version,
    loadPackage,
    isPyProxy,
    runPython,
    runPythonAsync,
    registerJsModule,
    unregisterJsModule,
    setInterruptBuffer,
    checkInterrupt,
    toPy,
    pyimport,
    unpackArchive,
    mountNativeFS,
    registerComlink,
    PythonError,
    PyBuffer,
    _module: Module,
    _api: API,
  };

  API.public_api = namespace;
  return namespace;
};
