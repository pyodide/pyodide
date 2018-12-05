// Regexps for validating package name and URI
const NAME_REGEXP = '[a-z0-9_][a-z0-9_\-]*'
const PACKAGE_URI_REGEXP = new RegExp(`^https?://.*?(${NAME_REGEXP}).js$`, 'i');
const PACKAGE_NAME_REGEXP = new RegExp(`^${NAME_REGEXP}$`, 'i');

// Browser flags
const IS_FIREFOX = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;

/**
 * The pyodide public API
 */
const PYODIDE_PUBLIC_API = [
  'loadPackage',
  'loadedPackages',
  'pyimport',
  'repr',
  'runPython',
  'runPythonAsync',
  'version',
];


/**
 * Generate a unique package name from URI
 * @param {string} uri The package URI
 * @returns {string | null} The package name inferred from the URI
 */
function uriToPackageName(uri) {
  if (PACKAGE_NAME_REGEXP.test(uri)) {
    return uri;
  } else if (PACKAGE_URI_REGEXP.test(uri)) {
    let match = PACKAGE_URI_REGEXP.exec(uri);
    // Get the regexp group corresponding to the package name
    return match[1];
  } else {
    return null;
  }
}

/**
 * Iodide-specific functionality, that doesn't make sense
 * if not using with Iodide.
 * TODO: Move this to the Iodide project  
 */
function initializeIodide() {
  if (window.iodide !== undefined) {
    // Load the custom CSS for Pyodide
    let link = document.createElement('link');
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.href = `${baseURL}renderedhtml.css`;
    document.getElementsByTagName('head')[0].appendChild(link);

    // Add a custom output handler for Python objects
    window.iodide.addOutputHandler({
      shouldHandle: (val) => {
        return (typeof val === 'function' &&
          pyodide._module.PyProxy.isPyProxy(val));
      },

      render: (val) => {
        let div = document.createElement('div');
        div.className = 'rendered_html';
        var element;
        if (val._repr_html_ !== undefined) {
          let result = val._repr_html_();
          if (typeof result === 'string') {
            div.appendChild(new DOMParser()
              .parseFromString(result, 'text/html')
              .body.firstChild);
            element = div;
          } else {
            element = result;
          }
        } else {
          let pre = document.createElement('pre');
          pre.textContent = val.toString();
          div.appendChild(pre);
          element = div;
        }
        return element;
      }
    });
  }
}

/**
 * The Javascript/Wasm call stack may be too small to handle the default
 * Python call stack limit of 1000 frames. This is generally the case on
 * Chrom(ium), but not on Firefox. Here, we determine the Javascript call
 * stack depth available, and then divide by 50 (determined heuristically)
 * to set the maximum Python call stack depth.
 * @param {*} pyodide 
 */
function fixRecursionLimit(pyodide) {
  let depth = 0;
  function recurse() {
    depth += 1;
    recurse();
  }
  try {
    recurse();
  } catch {
    ;
  }

  let recursionLimit = depth / 50;
  if (recursionLimit > 1000) {
    recursionLimit = 1000;
  }
  pyodide.runPython(`import sys; sys.setrecursionlimit(int(${recursionLimit}))`);
}

/**
 * Rearrange namespace for public API
 * @param {*} module 
 * @param {string[]} api 
 */
function makePublicAPI(module, api) {
  const namespace = { _module: module };
  for (const name of api) {
    namespace[name] = module[name];
  }
  return namespace;
}

/**
 * Embeds the pyodide ASM scripts onto the page
 * @param {string} baseURL 
 * @param {*} Module 
 */
function embedPyodideScripts(baseURL, Module) {
  let loadPackagePromise = Promise.resolve();

  // clang-format off
  let preloadWasm = () => {
    // On Chrome, we have to instantiate wasm asynchronously. Since that
    // can't be done synchronously within the call to dlopen, we instantiate
    // every .so that comes our way up front, caching it in the
    // `preloadedWasm` dictionary.

    let promise = new Promise((resolve) => resolve());
    let FS = pyodide._module.FS;

    function recurseDir(rootpath) {
      let dirs;
      try {
        dirs = FS.readdir(rootpath);
      } catch {
        return;
      }
      for (entry of dirs) {
        if (entry.startsWith('.')) {
          continue;
        }
        const path = rootpath + entry;
        if (entry.endsWith('.so')) {
          if (Module['preloadedWasm'][path] === undefined) {
            promise = promise
              .then(() => Module['loadWebAssemblyModule'](
                FS.readFile(path), true))
              .then((module) => {
                Module['preloadedWasm'][path] = module;
              });
          }
        } else if (FS.isDir(FS.lookupPath(path).node.mode)) {
          recurseDir(path + '/');
        }
      }
    }

    recurseDir('/');

    return promise;
  }
  // clang-format on

  /**
   * The package names to load
   * @param {string[]} names 
   * @param {*} messageCallback 
   */
  let _loadPackage = (names, messageCallback) => {
    // DFS to find all dependencies of the requested packages
    let packages = window.pyodide._module.packages.dependencies;
    let loadedPackages = window.pyodide.loadedPackages;
    let queue = [].concat(names || []);
    let toLoad = new Array();
    while (queue.length) {
      let uri = queue.pop();
      const package = uriToPackageName(uri);

      if (package == null) {
        console.error(`Invalid package name or URI '${uri}'`);
        return;
      } else if (package == uri) {
        uri = 'default channel';
      }

      if (package in loadedPackages) {
        if (uri != loadedPackages[package]) {
          console.error(`URI mismatch, attempting to load package ` +
            `${package} from ${uri} while it is already ` +
            `loaded from ${loadedPackages[package]}!`);
          return;
        }
      } else if (package in toLoad) {
        if (uri != toLoad[package]) {
          console.error(`URI mismatch, attempting to load package ` +
            `${package} from ${uri} while it is already ` +
            `being loaded from ${toLoad[package]}!`);
          return;
        }
      } else {
        console.log(`Loading ${package} from ${uri}`);

        toLoad[package] = uri;
        if (packages.hasOwnProperty(package)) {
          packages[package].forEach((subpackage) => {
            if (!(subpackage in loadedPackages) && !(subpackage in toLoad)) {
              queue.push(subpackage);
            }
          });
        } else {
          console.error(`Unknown package '${package}'`);
          return;
        }
      }
    }

    window.pyodide._module.locateFile = (path) => {
      // handle packages loaded from custom URLs
      let package = path.replace(/\.data$/, "");
      if (package in toLoad) {
        let uri = toLoad[package];
        if (uri != 'default channel') {
          return uri.replace(/\.js$/, ".data");
        };
      };
      return baseURL + path;
    };

    let promise = new Promise((resolve, reject) => {
      if (Object.keys(toLoad).length === 0) {
        resolve('No new packages to load');
        return;
      }

      const packageList = Array.from(Object.keys(toLoad)).join(', ');
      if (messageCallback !== undefined) {
        messageCallback(`Loading ${packageList}`);
      }

      window.pyodide._module.monitorRunDependencies = (n) => {
        if (n === 0) {
          for (let package in toLoad) {
            window.pyodide.loadedPackages[package] = toLoad[package];
          }
          delete window.pyodide._module.monitorRunDependencies;
          if (!IS_FIREFOX) {
            preloadWasm().then(() => { resolve(`Loaded ${packageList}`) });
          } else {
            resolve(`Loaded ${packageList}`);
          }
        }
      };

      for (let package in toLoad) {
        let script = document.createElement('script');
        let uri = toLoad[package];
        if (uri == 'default channel') {
          script.src = `${baseURL}${package}.js`;
        } else {
          script.src = `${uri}`;
        }
        script.onerror = (e) => { reject(e); };
        document.body.appendChild(script);
      }

      // We have to invalidate Python's import caches, or it won't
      // see the new files. This is done here so it happens in parallel
      // with the fetching over the network.
      window.pyodide.runPython('import importlib as _importlib\n' +
        '_importlib.invalidate_caches()\n');
    });

    if (window.iodide !== undefined) {
      window.iodide.evalQueue.await([promise]);
    }

    return promise;
  };

  /**
   * 
   * @param {string[]} names the module names
   * @param {*} messageCallback 
   */
  const loadPackage = (names, messageCallback) => {
    /* We want to make sure that only one loadPackage invocation runs at any
     * given time, so this creates a "chain" of promises. */
    loadPackagePromise =
      loadPackagePromise.then(() => _loadPackage(names, messageCallback));
    return loadPackagePromise;
  };

  const asmDataScript = document.createElement('script');
  asmDataScript.src = `${baseURL}pyodide.asm.data.js`;
  asmDataScript.onload = () => {
    const script = document.createElement('script');
    script.src = `${baseURL}pyodide.asm.js`;
    script.onload = () => {
      // The emscripten module needs to be at this location for the core
      // filesystem to install itself. Once that's complete, it will be replaced
      // by the call to `makePublicAPI` with a more limited public API.
      window.pyodide = pyodide(Module);
      window.pyodide.loadedPackages = new Array();
      window.pyodide.loadPackage = loadPackage;
    };
    document.head.appendChild(script);
  };

  document.head.appendChild(asmDataScript);
}

/**
 * A utility to externalize promise resolution
 */
function usePromise() {
  let resolver, rejecter
  const promise = new Promise((resolve, reject) => {
    resolver = resolve;
    rejecter = reject;
  })
  return [promise, resolver, rejecter]
}

/**
 * The main bootstrap script for loading pyodide.
 * 
 * @param {string} baseURL the base URL for pyodide scripts
 */
async function languagePluginLoader(baseURL = '{{DEPLOY}}') {
  // TODO: this string mangling should probably be done outside
  // of the loader function
  baseURL = baseURL.substr(0, baseURL.lastIndexOf('/')) + '/';

  const wasmURL = `${baseURL}pyodide.asm.wasm`;
  const wasmPromise = WebAssembly.compileStreaming(fetch(wasmURL));

  const [ postRunPromise, resolvePostRun ] = usePromise()
  const [ dataLoadPromise, resolveDataLoad ] = usePromise()

  let pyodideInstance

  const Module = {
    noImageDecoding: true,
    noAudioDecoding: true,
    noWasmDecoding: true,
    preloadedWasm: {},
    locateFile: path => baseURL + path,
    instantiateWasm(info, receiveInstance) {
      wasmPromise
        .then(module => WebAssembly.instantiate(module, info))
        .then(instance => receiveInstance(instance));
      return {};
    },
    postRun() {
      delete window.Module;
      fetch(`${baseURL}packages.json`)
        .then((response) => response.json())
        .then((json) => {
          fixRecursionLimit(window.pyodide);
          pyodideInstance = makePublicAPI(window.pyodide, PYODIDE_PUBLIC_API);
          pyodideInstance._module.packages = json;
          delete window.pyodide;
          resolvePostRun();
        });
    },
    monitorRunDependencies(n) {
      if (n === 0) {
        delete Module.monitorRunDependencies;
        resolveDataLoad();
      }
    },
  };
  window.Module = Module;

  embedPyodideScripts(baseURL, Module);

  // TODO: Move to iodide package
  initializeIodide()

  await Promise.all([postRunPromise, dataLoadPromise])

  // TODO: don't use a window global?
  window.pyodide = pyodideInstance
  return pyodideInstance
}

// TODO: use an ES export for this function instead of a window global
window.languagePluginLoader = languagePluginLoader
