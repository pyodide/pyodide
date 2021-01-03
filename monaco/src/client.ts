import * as monaco from 'monaco-editor';
import { MonacoServices, MonacoLanguageClient, ErrorAction, CloseAction, createConnection, OutputChannel, Message, DataCallback } from "monaco-languageclient";
import { createMessageConnection, MessageConnection, MessageReader, MessageWriter } from "vscode-jsonrpc"
import { WebWorkerMessageReader, WebWorkerMessageWriter } from "./messages";
import PylsWorker = require("worker-loader?name=[name].js!./pyls.worker");

const LANGUAGE_ID = 'python';
const MODEL_URI = 'inmemory://test.py'
const MONACO_URI = monaco.Uri.parse(MODEL_URI);

const pythonSource = `import sys

def print_version():
    print(sys.version)

print_version()
`;
const editor = monaco.editor.create(document.getElementById("container")!, {
    model: monaco.editor.createModel(pythonSource, LANGUAGE_ID, MONACO_URI),
    glyphMargin: true,
    lightbulb: {
        enabled: true
    }
});
(global as any).editor = editor;

// Install Monaco language client services and launch the language client
MonacoServices.install(editor);

// TODO(gatesn): dispose language client when python shuts down. Not sure how to get that hook
createLanguageClient().start();

function createLanguageClient(): MonacoLanguageClient {
    return new MonacoLanguageClient({
        name: "Pyodide Language Client",
        clientOptions: {
            // use a language id as a document selector
            documentSelector: ['python'],
            // TODO(gatesn): why?
            // disable the default error handler
            errorHandler: {
                error: () => ErrorAction.Continue,
                closed: () => CloseAction.DoNotRestart
            }
        },
        // create a language client connection from the JSON RPC connection on demand
        connectionProvider:  {
            get: async (errorHandler, closeHandler, outputChannel) => {
                const messageConnection = await createPyodideConnection(outputChannel);
                return createConnection(messageConnection, errorHandler, closeHandler);
            }
        }
    });
}

async function createPyodideConnection(_outputChannel: OutputChannel | undefined): Promise<MessageConnection> {
    const worker = new PylsWorker();
    const reader: MessageReader = new WebWorkerMessageReader(worker);
    const writer: MessageWriter = new WebWorkerMessageWriter(worker);
    return createMessageConnection(reader, writer);
}
