import { Module, API } from "./module.js";
import { TypedArray } from "./pyproxy.gen";

/**
 * Sets the interrupt buffer to be `interrupt_buffer`. This is only useful when
 * Pyodide is used in a webworker. The buffer should be a `SharedArrayBuffer`
 * shared with the main browser thread (or another worker). To request an
 * interrupt, a `2` should be written into `interrupt_buffer` (2 is the posix
 * constant for SIGINT).
 */
export function setInterruptBuffer(interrupt_buffer: TypedArray) {
  API.interrupt_buffer = interrupt_buffer;
  let status = !!interrupt_buffer;
  Module._set_pyodide_callback(status);
}

/**
 * Throws a KeyboardInterrupt error if a KeyboardInterrupt has been requested
 * via the interrupt buffer.
 *
 * This can be used to enable keyboard interrupts during execution of JavaScript
 * code, just as ``PyErr_CheckSignals`` is used to enable keyboard interrupts
 * during execution of C code.
 */
export function checkInterrupt() {
  if (!API.interrupt_buffer) {
    return;
  }
  Module._pyodide_check_interrupt();
  if (Module._PyErr_CheckSignals()) {
    Module._pythonexc2js();
  }
}

/**
 * This is a wrapper around setTimeout that runs `possiblyDelaySignals` first.
 *
 * This is used by webloop to schedule callbacks which are protected from
 * keyboard interrupts.
 *
 * @param callback
 * @param delay
 */
function scheduleWebloopHandle(handle: any, delay: number) {
  handle = handle.copy();
  setTimeout(() => {
    try {
      // If a keyboard interrupt happened while no synchronous code was
      // executing, it will most likely land here. We don't want the keyboard
      // interrupt to fire inside of our scheduling code.
      // Flush it!
      checkInterrupt();
    } catch (e) {}
    // To be extra careful, disable the interrupts until we enter the actual
    // scheduled callback (in webloopWrapCallback)
    API.interrupt_check_disabled = true;
    try {
      if (handle.cancelled()) {
        return;
      }
      handle._run();
    } finally {
      handle.destroy();
      // If handle wasn't cancelled, this was probably set to false inside of
      // webloopWrapCallback, but we want to be careful.
      API.interrupt_check_disabled = false;
    }
  }, delay);
}
API.scheduleWebloopHandle = scheduleWebloopHandle;

function wrapWebloopCallback(callback: any, context: any) {
  callback = callback.copy();
  context = context.copy();
  let result: any = (...args: any[]) => {
    let interrupt = false;
    try {
      interrupt = context.get(API.webloop._must_interrupt);
      if (interrupt) {
        // raise keyboard interrupt into callback
        Module._PyErr_SetInterrupt();
      }
      API.interrupt_check_disabled = false;
      callback(...args);
    } catch (e) {
      if (!interrupt || !e.message.includes("KeyboardInterrupt")) {
        // This shouldn't happen, it will get logged by the event loop as
        // something unexpected.
        throw e;
      } else {
        // Ignore the keyboard interrupt we intetionally raised into the
        // callback.
      }
    } finally {
      for (let arg of args) {
        if (API.isPyProxy(arg)) {
          arg.destroy();
        }
      }
      result.destroy();
    }
  };
  // If the handle is cancelled, we will invoke this cleanup method from Python.
  result.destroy = () => {
    callback.destroy();
    context.destroy();
  };
  return result;
}
API.wrapWebloopCallback = wrapWebloopCallback;
