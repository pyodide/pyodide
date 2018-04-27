var languagePluginLoader = new Promise((resolve, reject) => {
    let baseURL = "{{DEPLOY}}";
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
    };
    document.body.appendChild(script);

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
                        val['$$']['ptrType']['name'] === 'Py*');
            },

            render: (val) => {
                let div = document.createElement('div');
                div.className = 'rendered_html';
                if (val.hasattr('_repr_html_')) {
                    div.appendChild(new DOMParser().parseFromString(
                        val.getattr('_repr_html_').call([], {}), 'text/html').body.firstChild);
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
