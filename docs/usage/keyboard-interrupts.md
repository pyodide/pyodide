(interrupting_execution)=

# Interrupting execution

The native Python interrupt system is based on preemptive multitasking but Web
Assembly has no support for preemptive multitasking. Because of this,
interrupting execution in Pyodide must be achieved via a different mechanism
which takes some effort to set up.

## Setting up interrupts

In order to use interrupts you must be using Pyodide in a webworker.
You also will need to use a `SharedArrayBuffer`, which means that your server
must set appropriate security headers. See [the MDN
docs](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer#security_requirements)
for more information.

To use the interrupt system, you should create a `SharedArrayBuffer` on either
the main thread or the worker thread and share it with the other thread. You
should use {any}`pyodide.setInterruptBuffer` to set the interrupt buffer on the
Pyodide thread. When you want to indicate an interrupt, write a `2` into the
interrupt buffer. When the interrupt signal is processed, Pyodide will set the
value of the interrupt buffer back to `0`.

By default, when the interrupt fires, a `KeyboardInterrupt` is raised. [Using
the `signal`
module](https://docs.python.org/3/library/signal.html#signal.signal), it is
possible to register a custom Python function to handle `SIGINT`. If you
register a custom handler function it will be called instead.

Here is a very basic example. Main thread code:

```js
let pyodideWorker = new Worker("pyodideWorker.js");
let interruptBuffer = new Uint8Array(new SharedArrayBuffer(1));
pyodideWorker.postMessage({ cmd: "setInterruptBuffer", interruptBuffer });
function interruptExecution() {
  // 2 stands for SIGINT.
  interruptBuffer[0] = 2;
}
// imagine that interruptButton is a button we want to trigger an interrupt.
interruptButton.addEventListener("click", interruptExecution);
async function runCode(code) {
  // Clear interruptBuffer in case it was accidentally left set after previous code completed.
  interruptBuffer[0] = 0;
  pyodideWorker.postMessage({ cmd: "runCode", code });
}
```

Worker code:

```js
self.addEventListener("message", (msg) => {
  if (msg.data.cmd === "setInterruptBuffer") {
    pyodide.setInterruptBuffer(msg.data.interruptBuffer);
    return;
  }
  if (msg.data.cmd === "runCode") {
    pyodide.runPython(msg.data.code);
    return;
  }
});
```

## Allowing JavaScript code to be interrupted

The interrupt system above allows interruption of Python code and also of C code
that opts to allow itself to be interrupted by periodically calling
`PyErr_CheckSignals`. There is also a function {any}`pyodide.checkInterrupt` that
allows JavasSript functions called from Python to check for an interrupt. As a
simple example, we can implement an interruptable sleep function using
`Atomics.wait`:

```js
let blockingSleepBuffer = new Int32Array(new SharedArrayBuffer(4));
function blockingSleep(t) {
  for (let i = 0; i < t * 20; i++) {
    // This Atomics.wait call blocks the thread until the buffer changes or a 50ms timeout ellapses.
    // Since we won't change the value in the buffer, this blocks for 50ms.
    Atomics.wait(blockingSleepBuffer, 0, 0, 50);
    // Periodically check for an interrupt to allow a KeyboardInterrupt.
    pyodide.checkInterrupt();
  }
}
```
