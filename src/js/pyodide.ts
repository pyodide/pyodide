/**
 * The main bootstrap code for loading pyodide.
 */
import {
  calculateDirname,
  loadScript,
  initNodeModules,
  resolvePath,
  loadLockFile,
} from "./compat";

import { createSettings } from "./emscripten-settings";
import { version } from "./version";

import type { PyodideInterface } from "./api.js";
import type { TypedArray, Module } from "./types";
import type { EmscriptenSettings } from "./emscripten-settings";
import type { PackageData } from "./load-package";
import type { SnapshotConfig } from "./snapshot";
export type { PyodideInterface, TypedArray };

export { version, type PackageData };

declare function _createPyodideModule(
  settings: EmscriptenSettings,
): Promise<Module>;

/**
 * See documentation for loadPyodide.
 * @hidden
 */
export type ConfigType = {
  indexURL: string;
  packageCacheDir: string;
  lockFileURL: string;
  fullStdLib?: boolean;
  stdLibURL?: string;
  stdin?: () => string;
  stdout?: (msg: string) => void;
  stderr?: (msg: string) => void;
  jsglobals?: object;
  args: string[];
  _node_mounts: string[];
  env: { [key: string]: string };
  packages: string[];
  _makeSnapshot: boolean;
  enableRunUntilComplete: boolean;
  checkAPIVersion: boolean;
};

/**
 * Load the main Pyodide wasm module and initialize it.
 *
 * @returns The :ref:`js-api-pyodide` module.
 * @memberof globalThis
 * @async
 * @example
 * async function main() {
 *   const pyodide = await loadPyodide({
 *     fullStdLib: true,
 *     stdout: (msg) => console.log(`Pyodide: ${msg}`),
 *   });
 *   console.log("Loaded Pyodide");
 * }
 * main();
 */
export async function loadPyodide(
  options: {
    /**
     * The URL from which Pyodide will load the main Pyodide runtime and
     * packages. It is recommended that you leave this unchanged, providing an
     * incorrect value can cause broken behavior.
     *
     * Default: The url that Pyodide is loaded from with the file name
     * (``pyodide.js`` or ``pyodide.mjs``) removed.
     */
    indexURL?: string;

    /**
     * The file path where packages will be cached in node. If a package
     * exists in ``packageCacheDir`` it is loaded from there, otherwise it is
     * downloaded from the JsDelivr CDN and then cached into ``packageCacheDir``.
     * Only applies when running in node; ignored in browsers.
     *
     * Default: same as indexURL
     */
    packageCacheDir?: string;

    /**
     * The URL from which Pyodide will load the Pyodide ``pyodide-lock.json`` lock
     * file. You can produce custom lock files with :py:func:`micropip.freeze`.
     * Default: ```${indexURL}/pyodide-lock.json```
     */
    lockFileURL?: string;
    /**
     * Load the full Python standard library. Setting this to false excludes
     * unvendored modules from the standard library.
     * Default: ``false``
     */
    fullStdLib?: boolean;
    /**
     * The URL from which to load the standard library ``python_stdlib.zip``
     * file. This URL includes the most of the Python standard library. Some
     * stdlib modules were unvendored, and can be loaded separately
     * with ``fullStdLib: true`` option or by their package name.
     * Default: ```${indexURL}/python_stdlib.zip```
     */
    stdLibURL?: string;
    /**
     * Override the standard input callback. Should ask the user for one line of
     * input. The :js:func:`pyodide.setStdin` function is more flexible and
     * should be preferred.
     */
    stdin?: () => string;
    /**
     * Override the standard output callback. The :js:func:`pyodide.setStdout`
     * function is more flexible and should be preferred in most cases, but
     * depending on the ``args`` passed to ``loadPyodide``, Pyodide may write to
     * stdout on startup, which can only be controlled by passing a custom
     * ``stdout`` function.
     */
    stdout?: (msg: string) => void;
    /**
     * Override the standard error output callback. The
     * :js:func:`pyodide.setStderr` function is more flexible and should be
     * preferred in most cases, but depending on the ``args`` passed to
     * ``loadPyodide``, Pyodide may write to stdout on startup, which can only
     * be controlled by passing a custom ``stdout`` function.
     */
    stderr?: (msg: string) => void;
    /**
     * The object that Pyodide will use for the ``js`` module.
     * Default: ``globalThis``
     */
    jsglobals?: object;
    /**
     * Command line arguments to pass to Python on startup. See `Python command
     * line interface options
     * <https://docs.python.org/3.10/using/cmdline.html#interface-options>`_ for
     * more details. Default: ``[]``
     */
    args?: string[];
    /**
     * Environment variables to pass to Python. This can be accessed inside of
     * Python at runtime via :py:data:`os.environ`. Certain environment variables change
     * the way that Python loads:
     * https://docs.python.org/3.10/using/cmdline.html#environment-variables
     * Default: ``{}``.
     * If ``env.HOME`` is undefined, it will be set to a default value of
     * ``"/home/pyodide"``
     */
    env?: { [key: string]: string };
    /**
     * A list of packages to load as Pyodide is initializing.
     *
     * This is the same as loading the packages with
     * :js:func:`pyodide.loadPackage` after Pyodide is loaded except using the
     * ``packages`` option is more efficient because the packages are downloaded
     * while Pyodide bootstraps itself.
     */
    packages?: string[];
    /**
     * Opt into the old behavior where :js:func:`PyProxy.toString() <pyodide.ffi.PyProxy.toString>`
     * calls :py:func:`repr` and not :py:class:`str() <str>`.
     * @deprecated
     */
    pyproxyToStringRepr?: boolean;
    /**
     * Make loop.run_until_complete() function correctly using stack switching
     */
    enableRunUntilComplete?: boolean;
    /**
     * If true (default), throw an error if the version of Pyodide core does not
     * match the version of the Pyodide js package.
     */
    checkAPIVersion?: boolean;
    /**
     * Used by the cli runner. If we want to detect a virtual environment from
     * the host file system, it needs to be visible from when `main()` is
     * called. The directories in this list will be mounted at the same address
     * into the Emscripten file system so that virtual environments work in the
     * cli runner.
     * @ignore
     */
    _node_mounts?: string[];
    /**
     * @ignore
     */
    _makeSnapshot?: boolean;
    /**
     * @ignore
     */
    _loadSnapshot?:
      | Uint8Array
      | ArrayBuffer
      | PromiseLike<Uint8Array | ArrayBuffer>;
  } = {},
): Promise<PyodideInterface> {
  await initNodeModules();
  let indexURL = options.indexURL || (await calculateDirname());
  indexURL = resolvePath(indexURL); // A relative indexURL causes havoc.
  if (!indexURL.endsWith("/")) {
    indexURL += "/";
  }
  options.indexURL = indexURL;

  const default_config = {
    fullStdLib: false,
    jsglobals: globalThis,
    stdin: globalThis.prompt ? globalThis.prompt : undefined,
    lockFileURL: indexURL + "pyodide-lock.json",
    args: [],
    _node_mounts: [],
    env: {},
    packageCacheDir: indexURL,
    packages: [],
    enableRunUntilComplete: false,
    checkAPIVersion: true,
  };
  const config = Object.assign(default_config, options) as ConfigType;
  config.env.HOME ??= "/home/pyodide";
  /**
   * `PyErr_Print()` will call `exit()` if the exception is a `SystemError`.
   * This shuts down the Python interpreter, which is a change in behavior from
   * what happened before. In order to avoid this, we set the `inspect` config
   * parameter which prevents `PyErr_Print()` from calling `exit()`. Except in
   * the cli runner, we actually do want to exit. So set default to true and in
   * cli runner we explicitly set it to false.
   */
  config.env.PYTHONINSPECT ??= "1";
  const emscriptenSettings = createSettings(config);
  const API = emscriptenSettings.API;
  API.lockFilePromise = loadLockFile(config.lockFileURL);

  // If the pyodide.asm.js script has been imported, we can skip the dynamic import
  // Users can then do a static import of the script in environments where
  // dynamic importing is not allowed or not desirable, like module-type service workers
  if (typeof _createPyodideModule !== "function") {
    const scriptSrc = `${config.indexURL}pyodide.asm.js`;
    await loadScript(scriptSrc);
  }

  let snapshot: Uint8Array | undefined = undefined;
  if (options._loadSnapshot) {
    const snp = await options._loadSnapshot;
    if (ArrayBuffer.isView(snp)) {
      snapshot = snp;
    } else {
      snapshot = new Uint8Array(snp);
    }
    emscriptenSettings.noInitialRun = true;
    // @ts-ignore
    emscriptenSettings.INITIAL_MEMORY = snapshot.length;
  }

  // _createPyodideModule is specified in the Makefile by the linker flag:
  // `-s EXPORT_NAME="'_createPyodideModule'"`
  const Module = await _createPyodideModule(emscriptenSettings);
  // Handle early exit
  if (emscriptenSettings.exited) {
    throw emscriptenSettings.exited.toThrow;
  }
  if (options.pyproxyToStringRepr) {
    API.setPyProxyToStringMethod(true);
  }

  if (API.version !== version && config.checkAPIVersion) {
    throw new Error(`\
Pyodide version does not match: '${version}' <==> '${API.version}'. \
If you updated the Pyodide version, make sure you also updated the 'indexURL' parameter passed to loadPyodide.\
`);
  }
  // Disable further loading of Emscripten file_packager stuff.
  Module.locateFile = (path: string) => {
    throw new Error("Didn't expect to load any more file_packager files!");
  };

  let snapshotConfig: SnapshotConfig | undefined = undefined;
  if (snapshot) {
    snapshotConfig = API.restoreSnapshot(snapshot);
  }
  // runPython works starting after the call to finalizeBootstrap.
  const pyodide = API.finalizeBootstrap(snapshotConfig);
  API.sys.path.insert(0, API.config.env.HOME);

  if (!pyodide.version.includes("dev")) {
    // Currently only used in Node to download packages the first time they are
    // loaded. But in other cases it's harmless.
    API.setCdnUrl(`https://cdn.jsdelivr.net/pyodide/v${pyodide.version}/full/`);
  }
  API._pyodide.set_excepthook();
  await API.packageIndexReady;
  // I think we want this initializeStreams call to happen after
  // packageIndexReady? I don't remember why.
  API.initializeStreams(config.stdin, config.stdout, config.stderr);
  return pyodide;
}
