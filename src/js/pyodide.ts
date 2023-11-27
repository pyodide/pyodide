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

import { createModule, initializeFileSystem, preloadWasm } from "./module";
import { version } from "./version";

import type { PyodideInterface } from "./api.js";
import type { TypedArray, API, Module } from "./types";
import type { PackageData } from "./load-package";
export type { PyodideInterface, TypedArray };

export type {
  PyProxy,
  PyProxyWithLength,
  PyProxyWithGet,
  PyProxyWithSet,
  PyProxyWithHas,
  PyProxyDict,
  PyProxyIterable,
  PyProxyIterator,
  PyProxyAwaitable,
  PyProxyCallable,
  PyBuffer as PyProxyBuffer,
  PyBufferView as PyBuffer,
} from "generated/pyproxy";

export { version, type PackageData };

declare function _createPyodideModule(Module: any): Promise<void>;

/**
 * See documentation for loadPyodide.
 * @private
 */
export type ConfigType = {
  indexURL: string;
  packageCacheDir: string;
  lockFileURL: string;
  homedir: string;
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
 *     homedir: "/pyodide",
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
     * The home directory which Pyodide will use inside virtual file system.
     * This is deprecated, use ``{env: {HOME : some_dir}}`` instead.
     */
    homedir?: string;
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
     * Opt into the old behavior where PyProxy.toString calls `repr` and not
     * `str`.
     * @deprecated
     */
    pyproxyToStringRepr?: boolean;
    /**
     * @ignore
     */
    _node_mounts?: string[];
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
  };
  const config = Object.assign(default_config, options) as ConfigType;
  if (options.homedir) {
    console.warn(
      "The homedir argument to loadPyodide is deprecated. " +
        "Use 'env: { HOME: value }' instead of 'homedir: value'.",
    );
    if (options.env && options.env.HOME) {
      throw new Error("Set both env.HOME and homedir arguments");
    }
    config.env.HOME = config.homedir;
  }
  if (!config.env.HOME) {
    config.env.HOME = "/home/pyodide";
  }

  const Module = createModule();
  Module.print = config.stdout;
  Module.printErr = config.stderr;
  Module.arguments = config.args;

  const API = { config } as API;
  Module.API = API;
  API.lockFilePromise = loadLockFile(config.lockFileURL);

  preloadWasm(Module, indexURL);
  initializeFileSystem(Module, config);

  const moduleLoaded = new Promise((r) => (Module.postRun = r));

  // locateFile tells Emscripten where to find the data files that initialize
  // the file system.
  Module.locateFile = (path: string) => config.indexURL + path;

  // If the pyodide.asm.js script has been imported, we can skip the dynamic import
  // Users can then do a static import of the script in environments where
  // dynamic importing is not allowed or not desirable, like module-type service workers
  if (typeof _createPyodideModule !== "function") {
    const scriptSrc = `${config.indexURL}pyodide.asm.js`;
    await loadScript(scriptSrc);
  }

  // _createPyodideModule is specified in the Makefile by the linker flag:
  // `-s EXPORT_NAME="'_createPyodideModule'"`
  await _createPyodideModule(Module);

  // There is some work to be done between the module being "ready" and postRun
  // being called.
  await moduleLoaded;
  // Handle early exit
  if (Module.exited) {
    throw Module.exited.toThrow;
  }
  if (options.pyproxyToStringRepr) {
    API.setPyProxyToStringMethod(true);
  }

  if (API.version !== version) {
    throw new Error(
      `\
Pyodide version does not match: '${version}' <==> '${API.version}'. \
If you updated the Pyodide version, make sure you also updated the 'indexURL' parameter passed to loadPyodide.\
`,
    );
  }
  // Disable further loading of Emscripten file_packager stuff.
  Module.locateFile = (path: string) => {
    throw new Error("Didn't expect to load any more file_packager files!");
  };

  const pyodide = API.finalizeBootstrap();

  // runPython works starting here.
  if (!pyodide.version.includes("dev")) {
    // Currently only used in Node to download packages the first time they are
    // loaded. But in other cases it's harmless.
    API.setCdnUrl(`https://cdn.jsdelivr.net/pyodide/v${pyodide.version}/full/`);
  }
  await API.packageIndexReady;

  let importhook = API._pyodide._importhook;
  importhook.register_module_not_found_hook(
    API._import_name_to_package_name,
    API.lockfile_unvendored_stdlibs_and_test,
  );

  if (API.lockfile_info.version !== version) {
    throw new Error("Lock file version doesn't match Pyodide version");
  }
  API.package_loader.init_loaded_packages();
  if (config.fullStdLib) {
    await pyodide.loadPackage(API.lockfile_unvendored_stdlibs);
  }
  API.initializeStreams(config.stdin, config.stdout, config.stderr);
  return pyodide;
}
