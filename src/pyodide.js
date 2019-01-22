/**
 * The main bootstrap script for loading pyodide.
 */

var languagePluginLoader = new Promise((resolve, reject) => {
  // This is filled in by the Makefile to be either a local file or the
  // deployed location. TODO: This should be done in a less hacky
  // way.
  var baseURL = window.languagePluginUrl || '{{DEPLOY}}';
  baseURL = baseURL.substr(0, baseURL.lastIndexOf('/')) + '/';

  ////////////////////////////////////////////////////////////
  // Package loading
  let loadedPackages = new Array();
  var loadPackagePromise = new Promise((resolve) => resolve());
  // Regexp for validating package name and URI
  var package_name_regexp = '[a-z0-9_][a-z0-9_\-]*'
  var package_uri_regexp =
      new RegExp('^https?://.*?(' + package_name_regexp + ').js$', 'i');
  var package_name_regexp = new RegExp('^' + package_name_regexp + '$', 'i');

  let _uri_to_package_name = (package_uri) => {
    // Generate a unique package name from URI

    if (package_name_regexp.test(package_uri)) {
      return package_uri;
    } else if (package_uri_regexp.test(package_uri)) {
      let match = package_uri_regexp.exec(package_uri);
      // Get the regexp group corresponding to the package name
      return match[1];
    } else {
      return null;
    }
  };

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
                FS.readFile(path), {loadAsync: true}))
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

  let _loadPackage = (names, messageCallback) => {
    // DFS to find all dependencies of the requested packages
    let packages = window.pyodide._module.packages.dependencies;
    let loadedPackages = window.pyodide.loadedPackages;
    let queue = [].concat(names || []);
    let toLoad = new Array();
    while (queue.length) {
      let package_uri = queue.pop();

      const package = _uri_to_package_name(package_uri);

      if (package == null) {
        console.error(`Invalid package name or URI '${package_uri}'`);
        return;
      } else if (package == package_uri) {
        package_uri = 'default channel';
      }

      if (package in loadedPackages) {
        if (package_uri != loadedPackages[package]) {
          console.error(`URI mismatch, attempting to load package ` +
                        `${package} from ${package_uri} while it is already ` +
                        `loaded from ${loadedPackages[package]}!`);
          return;
        }
      } else if (package in toLoad) {
        if (package_uri != toLoad[package]) {
          console.error(`URI mismatch, attempting to load package ` +
                        `${package} from ${package_uri} while it is already ` +
                        `being loaded from ${toLoad[package]}!`);
          return;
        }
      } else {
        console.log(`Loading ${package} from ${package_uri}`);

        toLoad[package] = package_uri;
        if (packages.hasOwnProperty(package)) {
          packages[package].forEach((subpackage) => {
            if (!(subpackage in loadedPackages) && !(subpackage in toLoad)) {
              queue.push(subpackage);
            }
          });
        } else {
          console.error(`Unknown package '${package}'`);
        }
      }
    }

    window.pyodide._module.locateFile = (path) => {
      // handle packages loaded from custom URLs
      let package = path.replace(/\.data$/, "");
      if (package in toLoad) {
        let package_uri = toLoad[package];
        if (package_uri != 'default channel') {
          return package_uri.replace(/\.js$/, ".data");
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

      // monitorRunDependencies is called at the beginning and the end of each
      // package being loaded. We know we are done when it has been called
      // exactly "toLoad * 2" times.
      var packageCounter = Object.keys(toLoad).length * 2;

      window.pyodide._module.monitorRunDependencies = () => {
        packageCounter--;
        if (packageCounter === 0) {
          for (let package in toLoad) {
            window.pyodide.loadedPackages[package] = toLoad[package];
          }
          delete window.pyodide._module.monitorRunDependencies;
          window.removeEventListener('error', windowErrorHandler);
          if (!isFirefox) {
            preloadWasm().then(() => {resolve(`Loaded ${packageList}`)});
          } else {
            resolve(`Loaded ${packageList}`);
          }
        }
      };

      // Add a handler for any exceptions that are thrown in the process of
      // loading a package
      var windowErrorHandler = (err) => {
        delete window.pyodide._module.monitorRunDependencies;
        window.removeEventListener('error', windowErrorHandler);
        // Set up a new Promise chain, since this one failed
        loadPackagePromise = new Promise((resolve) => resolve());
        reject(err.message);
      };
      window.addEventListener('error', windowErrorHandler);

      for (let package in toLoad) {
        let script = document.createElement('script');
        let package_uri = toLoad[package];
        if (package_uri == 'default channel') {
          script.src = `${baseURL}${package}.js`;
        } else {
          script.src = `${package_uri}`;
        }
        script.onerror = (e) => {
          // If the package_uri fails to load, call monitorRunDependencies twice
          // (so packageCounter will still hit 0 and finish loading), and remove
          // the package from toLoad so we don't mark it as loaded.
          console.error(`Couldn't load package from URL ${script.src}`)
          let index = toLoad.indexOf(package);
          if (index !== -1) {
            toLoad.splice(index, 1);
          }
          for (let i = 0; i < 2; i++) {
            window.pyodide._module.monitorRunDependencies();
          }
        };
        document.body.appendChild(script);
      }

      // We have to invalidate Python's import caches, or it won't
      // see the new files. This is done here so it happens in parallel
      // with the fetching over the network.
      window.pyodide.runPython('import importlib as _importlib\n' +
                               '_importlib.invalidate_caches()\n');
    });

    return promise;
  };

  let loadPackage = (names, messageCallback) => {
    /* We want to make sure that only one loadPackage invocation runs at any
     * given time, so this creates a "chain" of promises. */
    loadPackagePromise =
        loadPackagePromise.then(() => _loadPackage(names, messageCallback));
    return loadPackagePromise;
  };

  ////////////////////////////////////////////////////////////
  // Fix Python recursion limit
  function fixRecursionLimit(pyodide) {
    // The Javascript/Wasm call stack may be too small to handle the default
    // Python call stack limit of 1000 frames. This is generally the case on
    // Chrom(ium), but not on Firefox. Here, we determine the Javascript call
    // stack depth available, and then divide by 50 (determined heuristically)
    // to set the maximum Python call stack depth.

    let depth = 0;
    function recurse() {
      depth += 1;
      recurse();
    }
    try {
      recurse();
    } catch (err) {
      ;
    }

    let recursionLimit = depth / 50;
    if (recursionLimit > 1000) {
      recursionLimit = 1000;
    }
    pyodide.runPython(
        `import sys; sys.setrecursionlimit(int(${recursionLimit}))`);
  };

  ////////////////////////////////////////////////////////////
  // Rearrange namespace for public API
  let PUBLIC_API = [
    'globals',
    'loadPackage',
    'loadedPackages',
    'pyimport',
    'repr',
    'runPython',
    'runPythonAsync',
    'checkABI',
    'version',
  ];

  function makePublicAPI(module, public_api) {
    var namespace = {_module : module};
    for (let name of public_api) {
      namespace[name] = module[name];
    }
    return namespace;
  }

  ////////////////////////////////////////////////////////////
  // Loading Pyodide
  let wasmURL = `${baseURL}pyodide.asm.wasm`;
  let Module = {};
  window.Module = Module;

  Module.noImageDecoding = true;
  Module.noAudioDecoding = true;
  Module.noWasmDecoding = true;
  Module.preloadedWasm = {};
  let isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;

  let wasm_promise = WebAssembly.compileStreaming(fetch(wasmURL));
  Module.instantiateWasm = (info, receiveInstance) => {
    wasm_promise.then(module => WebAssembly.instantiate(module, info))
        .then(instance => receiveInstance(instance));
    return {};
  };

  Module.checkABI = function(ABI_number) {
    if (ABI_number !== parseInt('{{ABI}}')) {
      throw `ABI numbers differ. Expected {{ABI}}, got ${ABI_number}`;
    }
    return true;
  };

  Module.locateFile = (path) => baseURL + path;
  var postRunPromise = new Promise((resolve, reject) => {
    Module.postRun = () => {
      delete window.Module;
      fetch(`${baseURL}packages.json`)
          .then((response) => response.json())
          .then((json) => {
            fixRecursionLimit(window.pyodide);
            window.pyodide.globals =
                window.pyodide.runPython('import sys\nsys.modules["__main__"]');
            window.pyodide = makePublicAPI(window.pyodide, PUBLIC_API);
            window.pyodide._module.packages = json;
            resolve();
          });
    };
  });

  var dataLoadPromise = new Promise((resolve, reject) => {
    Module.monitorRunDependencies =
        (n) => {
          if (n === 0) {
            delete Module.monitorRunDependencies;
            resolve();
          }
        }
  });

  Promise.all([ postRunPromise, dataLoadPromise ]).then(() => resolve());

  let data_script = document.createElement('script');
  data_script.src = `${baseURL}pyodide.asm.data.js`;
  data_script.onload = (event) => {
    let script = document.createElement('script');
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

  document.head.appendChild(data_script);

  ////////////////////////////////////////////////////////////
  // Iodide-specific functionality, that doesn't make sense
  // if not using with Iodide.
  if (window.iodide !== undefined) {
    // Load the custom CSS for Pyodide
    let link = document.createElement('link');
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.href = `${baseURL}renderedhtml.css`;
    document.getElementsByTagName('head')[0].appendChild(link);

    // Add a custom output handler for Python objects
    window.iodide.addOutputHandler({
      shouldHandle : (val) => {
        return (typeof val === 'function' &&
                pyodide._module.PyProxy.isPyProxy(val));
      },

      render : (val) => {
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
});
languagePluginLoader
