declare var Module: any;
declare var Tests: any;
declare var API: any;

import {
  IN_NODE,
  nodeFsPromisesMod,
  loadBinaryFile,
  initNodeModules,
  resolvePath,
} from "./compat.js";
import { PyProxy, isPyProxy } from "./pyproxy.gen";

/**
 * Initialize the packages index. This is called as early as possible in
 * loadPyodide so that fetching repodata.json can occur in parallel with other
 * operations.
 * @param lockFileURL
 * @private
 */
async function initializePackageIndex(lockFileURL: string) {
  let repodata;
  if (IN_NODE) {
    await initNodeModules();
    const package_string = await nodeFsPromisesMod.readFile(lockFileURL);
    repodata = JSON.parse(package_string);
  } else {
    let response = await fetch(lockFileURL);
    repodata = await response.json();
  }
  if (!repodata.packages) {
    throw new Error(
      "Loaded repodata.json does not contain the expected key 'packages'.",
    );
  }
  API.repodata_info = repodata.info;
  API.repodata_packages = repodata.packages;

  // compute the inverted index for imports to package names
  API._import_name_to_package_name = new Map();
  for (let name of Object.keys(API.repodata_packages)) {
    for (let import_name of API.repodata_packages[name].imports) {
      API._import_name_to_package_name.set(import_name, name);
    }
  }
}

API.packageIndexReady = initializePackageIndex(API.config.lockFileURL);

/**
 * Only used in Node. If we can't find a package in node_modules, we'll use this
 * to fetch the package from the cdn (and we'll store it into node_modules so
 * subsequent loads don't require a web request).
 * @private
 */
let cdnURL: string;
API.setCdnUrl = function (url: string) {
  cdnURL = url;
};

//
// Dependency resolution
//
const DEFAULT_CHANNEL = "default channel";
// Regexp for validating package name and URI
const package_uri_regexp = /^.*?([^\/]*)\.whl$/;

function _uri_to_package_name(package_uri: string): string | undefined {
  let match = package_uri_regexp.exec(package_uri);
  if (match) {
    let wheel_name = match[1].toLowerCase();
    return wheel_name.split("-").slice(0, -4).join("-");
  }
}

type PackageLoadMetadata = {
  name: string;
  channel: string;
  depends: string[];
  done: ResolvablePromise;
  installPromise?: Promise<void>;
};

interface ResolvablePromise extends Promise<void> {
  resolve: (value?: any) => void;
  reject: (err?: Error) => void;
}

function createDonePromise(): ResolvablePromise {
  let _resolve: (value: any) => void = () => {};
  let _reject: (err: Error) => void = () => {};

  const p: any = new Promise<void>((resolve, reject) => {
    _resolve = resolve;
    _reject = reject;
  });

  p.resolve = _resolve;
  p.reject = _reject;
  return p;
}

/**
 * Recursively add a package and its dependencies to toLoad.
 * A helper function for recursiveDependencies.
 * @param name The package to add
 * @param toLoad The set of names of packages to load
 * @private
 */
function addPackageToLoad(
  name: string,
  toLoad: Map<string, PackageLoadMetadata>,
) {
  name = name.toLowerCase();
  if (toLoad.has(name)) {
    return;
  }
  const pkg_info = API.repodata_packages[name];
  if (!pkg_info) {
    throw new Error(`No known package with name '${name}'`);
  }

  toLoad.set(name, {
    name: name,
    channel: DEFAULT_CHANNEL,
    depends: pkg_info.depends,
    installPromise: undefined,
    done: createDonePromise(),
  });

  // If the package is already loaded, we don't add dependencies, but warn
  // the user later. This is especially important if the loaded package is
  // from a custom url, in which case adding dependencies is wrong.
  if (loadedPackages[name] !== undefined) {
    return;
  }

  for (let dep_name of pkg_info.depends) {
    addPackageToLoad(dep_name, toLoad);
  }
}

/**
 * Calculate the dependencies of a set of packages
 * @param names The list of names whose dependencies we need to calculate.
 * @returns The map of package names to PackageLoadMetadata
 * @private
 */
function recursiveDependencies(
  names: string[],
  errorCallback: (err: string) => void,
): Map<string, PackageLoadMetadata> {
  const toLoad: Map<string, PackageLoadMetadata> = new Map();
  for (let name of names) {
    const pkgname = _uri_to_package_name(name);
    if (pkgname === undefined) {
      addPackageToLoad(name, toLoad);
      continue;
    }

    const channel = name;

    if (toLoad.has(pkgname) && toLoad.get(pkgname)!.channel !== channel) {
      errorCallback(
        `Loading same package ${pkgname} from ${channel} and ${
          toLoad.get(pkgname)!.channel
        }`,
      );
      continue;
    }
    toLoad.set(pkgname, {
      name: pkgname,
      channel: channel, // name is url in this case
      depends: [],
      installPromise: undefined,
      done: createDonePromise(),
    });
  }
  return toLoad;
}

//
// Dependency download and install
//

/**
 * Download a package. If `channel` is `DEFAULT_CHANNEL`, look up the wheel URL
 * relative to indexURL from `repodata.json`, otherwise use the URL specified by
 * `channel`.
 * @param name The name of the package
 * @param channel Either `DEFAULT_CHANNEL` or the absolute URL to the
 * wheel or the path to the wheel relative to indexURL.
 * @returns The binary data for the package
 * @private
 */
async function downloadPackage(
  name: string,
  channel: string,
): Promise<Uint8Array> {
  let file_name, uri, file_sub_resource_hash;
  if (channel === DEFAULT_CHANNEL) {
    if (!(name in API.repodata_packages)) {
      throw new Error(`Internal error: no entry for package named ${name}`);
    }
    file_name = API.repodata_packages[name].file_name;
    uri = resolvePath(file_name, API.config.indexURL);
    file_sub_resource_hash = API.package_loader.sub_resource_hash(
      API.repodata_packages[name].sha256,
    );
  } else {
    uri = channel;
    file_sub_resource_hash = undefined;
  }
  try {
    return await loadBinaryFile(uri, file_sub_resource_hash);
  } catch (e) {
    if (!IN_NODE || channel !== DEFAULT_CHANNEL) {
      throw e;
    }
  }
  console.log(
    `Didn't find package ${file_name} locally, attempting to load from ${cdnURL}`,
  );
  // If we are IN_NODE, download the package from the cdn, then stash it into
  // the node_modules directory for future use.
  let binary = await loadBinaryFile(cdnURL + file_name);
  console.log(
    `Package ${file_name} loaded from ${cdnURL}, caching the wheel in node_modules for future use.`,
  );
  await nodeFsPromisesMod.writeFile(uri, binary);
  return binary;
}

/**
 * Install the package into the file system.
 * @param name The name of the package
 * @param buffer The binary data returned by downloadPackage
 * @private
 */
async function installPackage(
  name: string,
  buffer: Uint8Array,
  channel: string,
) {
  let pkg = API.repodata_packages[name];
  if (!pkg) {
    pkg = {
      file_name: ".whl",
      shared_library: false,
      depends: [],
      imports: [] as string[],
    };
  }
  const filename = pkg.file_name;
  // This Python helper function unpacks the buffer and lists out any .so files in it.
  const dynlibs = API.package_loader.unpack_buffer.callKwargs({
    buffer,
    filename,
    target: pkg.install_dir,
    calculate_dynlibs: true,
    installer: "pyodide.loadPackage",
    source: channel === DEFAULT_CHANNEL ? "pyodide" : channel,
  });
  for (const dynlib of dynlibs) {
    await loadDynlib(dynlib, pkg.shared_library);
  }
}

/**
 * Download and install the package.
 * Downloads can be done in parallel, but installs must be done for dependencies first.
 * @param name The name of the package
 * @param toLoad The map of package names to PackageLoadMetadata
 * @param loaded The set of loaded package names, this will be updated by this function.
 * @param failed The map of <failed package name, error message>, this will be updated by this function.
 * @private
 */
async function downloadAndInstall(
  name: string,
  toLoad: Map<string, PackageLoadMetadata>,
  loaded: Set<string>,
  failed: Map<string, Error>,
) {
  if (loadedPackages[name] !== undefined) {
    return;
  }

  const pkg = toLoad.get(name)!;

  try {
    const buffer = await downloadPackage(pkg.name, pkg.channel);
    const installPromisDependencies = pkg.depends.map((dependency) => {
      return toLoad.has(dependency)
        ? toLoad.get(dependency)!.done
        : Promise.resolve();
    });

    // wait until all dependencies are installed
    await Promise.all(installPromisDependencies);

    await installPackage(pkg.name, buffer, pkg.channel);
    loaded.add(pkg.name);
    loadedPackages[pkg.name] = pkg.channel;
  } catch (err: any) {
    failed.set(name, err);
    // We don't throw error when loading a package fails, but just report it.
    // pkg.done.reject(err);
  } finally {
    pkg.done.resolve();
  }
}

/**
 * @returns A new asynchronous lock
 * @private
 */
function createLock() {
  // This is a promise that is resolved when the lock is open, not resolved when lock is held.
  let _lock = Promise.resolve();

  /**
   * Acquire the async lock
   * @returns A zero argument function that releases the lock.
   * @private
   */
  async function acquireLock() {
    const old_lock = _lock;
    let releaseLock: () => void;
    _lock = new Promise((resolve) => (releaseLock = resolve));
    await old_lock;
    // @ts-ignore
    return releaseLock;
  }
  return acquireLock;
}

// Emscripten has a lock in the corresponding code in library_browser.js. I
// don't know why we need it, but quite possibly bad stuff will happen without
// it.
const acquireDynlibLock = createLock();

/**
 * Load a dynamic library. This is an async operation and Python imports are
 * synchronous so we have to do it ahead of time. When we add more support for
 * synchronous I/O, we could consider doing this later as a part of a Python
 * import hook.
 *
 * @param lib The file system path to the library.
 * @param shared Is this a shared library or not?
 * @private
 */
async function loadDynlib(lib: string, shared: boolean) {
  const releaseDynlibLock = await acquireDynlibLock();
  const loadGlobally = shared;

  // This is a fake FS-like object to make emscripten
  // load shared libraries from the file system.
  const libraryFS = {
    _ldLibraryPaths: ["/usr/lib", API.sitepackages],
    _resolvePath: (path: string) => {
      if (Module.PATH.isAbs(path)) {
        if (Module.FS.findObject(path) !== null) {
          return path;
        }

        // If the path is absolute but doesn't exist, we try to find it from
        // the library paths.
        path = path.substring(path.lastIndexOf("/") + 1);
      }

      for (const dir of libraryFS._ldLibraryPaths) {
        const fullPath = Module.PATH.join2(dir, path);
        if (Module.FS.findObject(fullPath) !== null) {
          return fullPath;
        }
      }
      return path;
    },
    findObject: (path: string, dontResolveLastLink: boolean) =>
      Module.FS.findObject(libraryFS._resolvePath(path), dontResolveLastLink),
    readFile: (path: string) =>
      Module.FS.readFile(libraryFS._resolvePath(path)),
  };

  try {
    await Module.loadDynamicLibrary(lib, {
      loadAsync: true,
      nodelete: true,
      global: loadGlobally,
      fs: libraryFS,
    });
  } catch (e: any) {
    if (e && e.message && e.message.includes("need to see wasm magic number")) {
      console.warn(
        `Failed to load dynlib ${lib}. We probably just tried to load a linux .so file or something.`,
      );
      return;
    }
    throw e;
  } finally {
    releaseDynlibLock();
  }
}
API.loadDynlib = loadDynlib;

const acquirePackageLock = createLock();

/**
 * Load a package or a list of packages over the network. This installs the
 * package in the virtual filesystem. The package needs to be imported from
 * Python before it can be used.
 *
 * @param names Either a single package name or
 * URL or a list of them. URLs can be absolute or relative. The URLs must have
 * file name ``<package-name>.js`` and there must be a file called
 * ``<package-name>.data`` in the same directory. The argument can be a
 * ``PyProxy`` of a list, in which case the list will be converted to JavaScript
 * and the ``PyProxy`` will be destroyed.
 * @param messageCallback A callback, called with progress messages
 *    (optional)
 * @param errorCallback A callback, called with error/warning messages
 *    (optional)
 * @async
 */
export async function loadPackage(
  names: string | PyProxy | Array<string>,
  messageCallback?: (msg: string) => void,
  errorCallback?: (msg: string) => void,
) {
  messageCallback = messageCallback || console.log;
  errorCallback = errorCallback || console.error;
  if (isPyProxy(names)) {
    names = names.toJs();
  }
  if (!Array.isArray(names)) {
    names = [names as string];
  }

  const toLoad = recursiveDependencies(names, errorCallback);

  for (const [pkg, pkg_metadata] of toLoad) {
    const loaded = loadedPackages[pkg];
    if (loaded === undefined) {
      continue;
    }
    toLoad.delete(pkg);
    // If uri is from the DEFAULT_CHANNEL, we assume it was added as a
    // dependency, which was previously overridden.
    if (
      loaded === pkg_metadata.channel ||
      pkg_metadata.channel === DEFAULT_CHANNEL
    ) {
      messageCallback(`${pkg} already loaded from ${loaded}`);
    } else {
      errorCallback(
        `URI mismatch, attempting to load package ${pkg} from ${pkg_metadata.channel} ` +
          `while it is already loaded from ${loaded}. To override a dependency, ` +
          `load the custom package first.`,
      );
    }
  }

  if (toLoad.size === 0) {
    messageCallback("No new packages to load");
    return;
  }

  const packageNames = [...toLoad.keys()].join(", ");
  const loaded = new Set<string>();
  const failed = new Map<string, Error>();
  const releaseLock = await acquirePackageLock();
  try {
    messageCallback(`Loading ${packageNames}`);
    for (const [name] of toLoad) {
      if (loadedPackages[name]) {
        // Handle the race condition where the package was loaded between when
        // we did dependency resolution and when we acquired the lock.
        toLoad.delete(name);
        continue;
      }

      // TODO: add support for prefetching modules by awaiting on a promise right
      // here which resolves in loadPyodide when the bootstrap is done.
      toLoad.get(name)!.installPromise = downloadAndInstall(
        name,
        toLoad,
        loaded,
        failed,
      );
    }

    await Promise.all(
      Array.from(toLoad.values()).map(({ installPromise }) => installPromise),
    );

    Module.reportUndefinedSymbols();
    if (loaded.size > 0) {
      const successNames = Array.from(loaded).join(", ");
      messageCallback(`Loaded ${successNames}`);
    }

    if (failed.size > 0) {
      const failedNames = Array.from(failed.keys()).join(", ");
      messageCallback(`Failed to load ${failedNames}`);
      for (const [name, err] of failed) {
        errorCallback(`The following error occurred while loading ${name}:`);
        errorCallback(err.message);
      }
    }

    // We have to invalidate Python's import caches, or it won't
    // see the new files.
    API.importlib.invalidate_caches();
  } finally {
    releaseLock();
  }
}

/**
 * The list of packages that Pyodide has loaded.
 * Use ``Object.keys(pyodide.loadedPackages)`` to get the list of names of
 * loaded packages, and ``pyodide.loadedPackages[package_name]`` to access
 * install location for a particular ``package_name``.
 */
export let loadedPackages: { [key: string]: string } = {};
