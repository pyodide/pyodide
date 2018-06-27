/**
 * The main bootstrap script for loading pyodide.
 */

var languagePluginLoader = new Promise((resolve, reject) => {
  // This is filled in by the Makefile to be either a local file or the
  // deployed location. TODO: This should be done in a less hacky
  // way.
  const baseURL = '{{DEPLOY}}';

  ////////////////////////////////////////////////////////////
  // Package loading
  var packages = undefined;
  let loadedPackages = new Set();

  let loadPackage = (names) => {
    // DFS to find all dependencies of the requested packages
    let packages = window.pyodide.packages.dependencies;
    let queue = new Array(names);
    let toLoad = new Set();
    while (queue.length) {
      const package = queue.pop();
      if (!loadedPackages.has(package)) {
        toLoad.add(package);
        if (packages.hasOwnProperty(package)) {
          packages[package].forEach((subpackage) => {
            if (!loadedPackages.has(subpackage) && !toLoad.has(subpackage)) {
              queue.push(subpackage);
            }
          });
        } else {
          console.log(`Unknown package '${package}'`);
        }
      }
    }

    let promise = new Promise((resolve, reject) => {
      if (toLoad.size === 0) {
        resolve('No new packages to load');
      }

      pyodide.monitorRunDependencies = (n) => {
        if (n === 0) {
          toLoad.forEach((package) => loadedPackages.add(package));
          delete pyodide.monitorRunDependencies;
          const packageList = Array.from(toLoad.keys()).join(', ');
          resolve(`Loaded ${packageList}`);
        }
      };

      toLoad.forEach((package) => {
        let script = document.createElement('script');
        script.src = `${baseURL}${package}.js`;
        script.onerror = (e) => { reject(e); };
        document.body.appendChild(script);
      });

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

  ////////////////////////////////////////////////////////////
  // Loading Pyodide
  let wasmURL = `${baseURL}pyodide.asm.wasm`;
  let Module = {};
  window.Module = Module;

  Module.noImageDecoding = true;
  Module.noAudioDecoding = true;
  let isFirefox = navigator.userAgent.toLowerCase().indexOf('firefox') > -1;
  if (isFirefox) {
    Module.noWasmDecoding = true;
  }

  let wasm_promise = WebAssembly.compileStreaming(fetch(wasmURL));
  Module.instantiateWasm = (info, receiveInstance) => {
    wasm_promise.then(module => WebAssembly.instantiate(module, info))
        .then(instance => receiveInstance(instance));
    return {};
  };

  Module.filePackagePrefixURL = baseURL;
  var postRunPromise = new Promise((resolve, reject) => {
    Module.postRun = () => {
      delete window.Module;
      fetch(`${baseURL}packages.json`)
        .then((response) => response.json())
        .then((json) => {
          window.pyodide.packages = json;
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
      window.pyodide = pyodide(Module);
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
        return (typeof val === 'function' && pyodide.PyProxy.isPyProxy(val));
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
