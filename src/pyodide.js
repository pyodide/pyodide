var languagePluginLoader = new Promise((resolve, reject) => {
    let baseURL = "{{DEPLOY}}";
    let wasmURL = `${baseURL}pyodide.asm.wasm?x=${Date.now()}`;
    let wasmXHR = new XMLHttpRequest();
    wasmXHR.open('GET', wasmURL, true);
    wasmXHR.responseType = 'arraybuffer';
    wasmXHR.onload = function() {
        let Module = {};

        if (wasmXHR.status === 200 || wasmXHR.status === 0) {
            Module.wasmBinary = wasmXHR.response;
        } else {
            console.warn(
                `Couldn't download the pyodide.asm.wasm binary.  Response was ${wasmXHR.status}`);
            reject();
        }

        Module.baseURL = baseURL;
        Module.postRun = () => {
            resolve();
        }
        let script = document.createElement('script');
        script.src = `${baseURL}pyodide.asm.js`;
        script.onload = () => {
            window.pyodide = pyodide(Module);
        };
        document.body.appendChild(script);
    };
    wasmXHR.send(null);

    if (window.iodide !== undefined) {
        const py_output_handler = {
            shouldHandle: (val) => {
                return (typeof val === 'object' &&
                        val['$$'] !== undefined &&
                        val['$$']['ptrType']['name'] === 'Py*');
            },

            render: (val) => {
                if (val.hasattr('to_html')) {
                    return new DOMParser().parseFromString(
                        val.getattr('to_html').call([], {}), 'text/html').body.firstChild;
                } else {
                    let pre = document.createElement('pre');
                    pre.textContent = window.pyodide.repr(val);
                    return pre;
                }
            }
        };
        window.iodide.addOutputHandler(py_output_handler);
    }
});
languagePluginLoader
