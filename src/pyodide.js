var languagePluginLoader = new Promise((resolve, reject) => {
    const baseURL = '{{DEPLOY}}';

    const packages = {
        'dateutil': [],
        'numpy': [],
        'pandas': ['numpy', 'dateutil', 'pytz'],
        'pytz': [],
    };
    let loadedPackages = new Set();
    let loadPackage = (names) => {
        if (Array.isArray(names)) {
            names = [names];
        }

        // DFS to find all dependencies of the requested packages
        let queue = new Array(names);
        let toLoad = new Set();
        while (queue.length) {
            const package = queue.pop();
            if (!packages.hasOwnProperty(package)) {
                throw `Unknown package '${package}'`;
            }
            if (!loadedPackages.has(package)) {
                toLoad.add(package);
                packages[package].forEach((subpackage) => {
                    if (!loadedPackages.has(subpackage) &&
                        !toLoad.has(subpackage)) {
                        queue.push(subpackage);
                    }
                });
            }
        }

        let promise = new Promise((resolve, reject) => {
            var n = toLoad.size;

            if (n === 0) {
                resolve('No new packages to load');
            }

            toLoad.forEach((package) => {
                let script = document.createElement('script');
                script.src = `${baseURL}${package}.js`;
                console.log(script.src);
                script.onload = (e) => {
                    n--;
                    loadedPackages.add(package);
                    if (n <= 0) {
                        // All of the requested packages are now loaded.
                        // We have to invalidate Python's import caches, or it won't
                        // see the new files.
                        window.pyodide.runPython(
                            'import importlib as _importlib\n' +
                            '_importlib.invalidate_caches()\n');
                        const packageList = Array.from(toLoad.keys()).join(', ');
                        resolve(`Loaded ${packageList}`);
                    }
                };
                script.onerror = (e) => {
                    reject(e);
                };
                document.body.appendChild(script);
            });
        });

        return promise;
    };

    let makeCallableProxy = (obj) => {
        var clone = obj.clone();
        function callProxy(args) {
            return clone.call(Array.from(arguments), {});
        };
        return callProxy;
    };

    let wasmURL = `${baseURL}pyodide.asm.wasm`;
    let Module = {};

    let wasm_promise = WebAssembly.compileStreaming(fetch(wasmURL));
    Module.instantiateWasm = (info, receiveInstance) => {
        wasm_promise
            .then(module => WebAssembly.instantiate(module, info))
            .then(instance => receiveInstance(instance));
        return {};
    };
    Module.filePackagePrefixURL = baseURL;
    Module.postRun = () => {
        resolve();
    };

    let script = document.createElement('script');
    script.src = `${baseURL}pyodide.asm.js`;
    script.onload = () => {
        window.pyodide = pyodide(Module);
        window.pyodide.loadPackage = loadPackage;
        window.pyodide.makeCallableProxy = makeCallableProxy;
    };
    document.head.appendChild(script);

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
                return (typeof val === 'object' &&
                        val['$$'] !== undefined &&
                        val['$$']['ptrType']['name'] === 'PyObject*');
            },

            render: (val) => {
                let div = document.createElement('div');
                div.className = 'rendered_html';
                if ('_repr_html_' in val) {
                    div.appendChild(new DOMParser().parseFromString(
                        val._repr_html_(), 'text/html').body.firstChild);
                } else {
                    let pre = document.createElement('pre');
                    pre.textContent = window.pyodide.repr(val);
                    div.appendChild(pre);
                }
                return div;
            }
        });
    }
});
languagePluginLoader
