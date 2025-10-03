import { RUNTIME_ENV } from "./environments";

const scheduleCallbackImmediateMessagePrefix =
  "sched$" + Math.random().toString(36).slice(2) + "$";

const tasks: Record<number, () => void> = {};
let nextTaskHandle = 0;

let sharedChannel: MessageChannel | null = null;

/**
 * Setup global message event listener to handle immediate callbacks
 */
function installPostMessageHandler() {
  if (!RUNTIME_ENV.IN_BROWSER_MAIN_THREAD) {
    return;
  }

  const onGlobalMessage = (event: MessageEvent) => {
    if (
      typeof event.data === "string" &&
      event.data.indexOf(scheduleCallbackImmediateMessagePrefix) === 0
    ) {
      const handle = +event.data.slice(
        scheduleCallbackImmediateMessagePrefix.length,
      );
      const task = tasks[handle];
      if (!task) {
        return;
      }

      try {
        task();
      } finally {
        delete tasks[handle];
      }
    }
  };

  globalThis.addEventListener("message", onGlobalMessage, false);
}

installPostMessageHandler();

function ensureSharedChannel() {
  if (sharedChannel) return;

  if (RUNTIME_ENV.IN_SAFARI || RUNTIME_ENV.IN_DENO) return;

  if (typeof globalThis.MessageChannel === "function") {
    sharedChannel = new MessageChannel();
    sharedChannel.port1.onmessage = (event: MessageEvent) => {
      const handle = event.data;
      const task = tasks[handle];
      if (!task) {
        return;
      }

      try {
        task();
      } finally {
        delete tasks[handle];
      }
    };
  }
}

ensureSharedChannel();

/**
 * Implementation of zero-delay scheduler for immediate callbacks
 * Try our best to use the fastest method available, based on the current environment.
 * This implementation is based on the following references:
 *   - https://github.com/YuzuJS/setImmediate
 *   - https://github.com/zloirock/core-js/blob/master/packages/core-js/internals/task.js
 * General notes:
 * - Promise.resolve().then() is not a good option. As it uses microtask queue unlike setTimeout which uses macrotask queue
 *   - Ref: https://github.com/YuzuJS/setImmediate/pull/56
 * - MessageChannel is faster (2-3x) than postMessage for Chrome, Firefox, and Node.js
 *   but it has some issues in Safari (slow and messes up the event loop), and Deno.
 *   - Ref: https://github.com/pyodide/pyodide/pull/4583
 *   - Ref: https://github.com/zloirock/core-js/issues/624
 *   - Ref: https://github.com/YuzuJS/setImmediate/issues/80
 */
function scheduleCallbackImmediate(callback: () => void) {
  if (RUNTIME_ENV.IN_NODE) {
    setImmediate(callback);
  } else if (sharedChannel) {
    tasks[nextTaskHandle] = callback;
    sharedChannel.port2.postMessage(nextTaskHandle);
    nextTaskHandle++;
  } else if (
    RUNTIME_ENV.IN_BROWSER_MAIN_THREAD &&
    typeof globalThis.postMessage === "function"
  ) {
    tasks[nextTaskHandle] = callback;
    globalThis.postMessage(
      scheduleCallbackImmediateMessagePrefix + nextTaskHandle,
      "*",
    );
    nextTaskHandle++;
  } else {
    setTimeout(callback, 0);
  }
}

/**
 * Schedule a callback. Supports both immediate and delayed callbacks.
 * @param callback The callback to be scheduled
 * @param timeout The delay in milliseconds before the callback is called
 * @hidden
 */
export function scheduleCallback(callback: () => void, timeout: number = 0) {
  if (timeout === 0) {
    // for delay 0, use immediate callback
    scheduleCallbackImmediate(callback);
  } else {
    setTimeout(callback, timeout);
  }
}
