const ctx: Worker = self as any;

importScripts("pyodide_dev.js");

declare var languagePluginLoader: Promise<void>;
declare var pyodide: {
    runPython(python: string): string;
    runPythonAsync(python: string): Promise<string>;
    pyimport<T>(variableName: string): T;
    loadPackage(package: string | string[]): Promise<void>;
};

const endpointPromise: Promise<any> = createPythonLanguageServer();

ctx.addEventListener("message", msg => {
    endpointPromise.then((endpoint) => endpoint.consume_string(JSON.stringify(msg.data)));
})

async function createPythonLanguageServer(): Promise<any> {
    await languagePluginLoader;
    await pyodide.loadPackage([
        "setuptools",
        "python-language-server",
        "python-jsonrpc-server",
        "pluggy", "jedi", "ujson", "parso",
        // Plugins
        "pycodestyle", "autopep8", "pyflakes"
    ]);
    pyodide.runPython(`
            from pyls import python_ls
            server = python_ls.PythonLanguageServer(None, None)
        `);
    const server = pyodide.pyimport<any>('server');

    // TODO(gatesn): the JS objects when passed into Python are missing several attributes required to parse messages (e.g. __contains__)
    // https://github.com/iodide-project/pyodide/issues/601
    pyodide.runPython(`
        import json
        from pyls_jsonrpc.endpoint import Endpoint

        class StringEndpoint(Endpoint):
            """Custom endpoint that parses JSON strings before consuming them."""

            def consume_string(self, msg_str):
                self.consume(json.loads(msg_str))
        `);

    const endpoint = pyodide.pyimport<any>("StringEndpoint")(server, (response: any) => {
        ctx.postMessage(response);
    });
    server._endpoint = endpoint;

    return endpoint;
}
