import { loadPyodide } from "./index";
const loadPromise = loadPyodide();

onmessage = async function(e: { data: any; }) { // eslint-disable-line no-unused-vars
    await loadPromise;

    const data = e.data;
    const keys = Object.keys(data);
    for (let key of keys) {
        if (key !== 'python') {
            // Keys other than python must be arguments for the python script.
            // Set them on self, so that `from js import key` works.
            self[key as any] = data[key];
        }
    }

    try {
        const results = await self.pyodide.runPythonAsync(data.python, () => {});
    } catch(err) {
        // if you prefer messages with the error
        (self as any).postMessage({error : err.message});
        // if you prefer onerror events
        // setTimeout(() => { throw err; });
    }
}