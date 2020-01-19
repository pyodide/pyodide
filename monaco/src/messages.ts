import { DataCallback, Message } from "monaco-languageclient";
import { AbstractMessageWriter } from "vscode-jsonrpc/lib/messageWriter";
import { AbstractMessageReader } from "vscode-jsonrpc/lib/messageReader";

export class WebWorkerMessageReader extends AbstractMessageReader {

    constructor(private readonly worker: Worker) {
        super();
    };

    public listen(callback: DataCallback): void {
        this.worker.addEventListener("message", msg => {
            console.debug("Got message from Python", msg.data);
            callback(msg.data);
        });
	}

}

export class WebWorkerMessageWriter extends AbstractMessageWriter {

    constructor(private readonly worker: Worker) {
        super();
    };

    public write(msg: Message): void {
        console.debug("Sending message to Python", msg);
        this.worker.postMessage(msg);
    }
}

