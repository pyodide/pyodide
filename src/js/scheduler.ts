import { IN_BROWSER_MAIN_THREAD, IN_NODE, IN_BROWSER_WEB_WORKER } from './environments';
// Implementation of zero-delay scheduler for immediate callbacks
// Notes for future reference:
// - This is a workaround for the throttling of setTimeout in modern browsers
// - Promise.resolve().then() is not a good option. As it uses microtask queue unlike setTimeout which uses macrotask queue
//   - Ref: https://github.com/YuzuJS/setImmediate/pull/56
// - MessageChannel works for Chrome, Firefox, and Node.js but it has some issues in Safari (slow and messes up the event loop), and Deno
//   - Ref: https://github.com/pyodide/pyodide/pull/4583
//   - Ref: https://github.com/zloirock/core-js/issues/624
//   - Ref: https://github.com/YuzuJS/setImmediate/issues/80
// - References for the implementation:
//   - https://github.com/YuzuJS/setImmediate
//   - https://github.com/zloirock/core-js/blob/master/packages/core-js/internals/task.js


const scheduleCallbackImmediateMessagePrefix = "sched$" + Math.random().toString(36).slice(2) + "$";
const tasks: Record<number, () => void> = {};
let nextTaskHandle = 0;

function installPostMessageHandler() {
    if (!IN_BROWSER_MAIN_THREAD) {
        return;
    }

    const onGlobalMessage = (event: MessageEvent) => {
        if (typeof event.data === "string" && event.data.indexOf(scheduleCallbackImmediateMessagePrefix) === 0) {
            const handle = +event.data.slice(scheduleCallbackImmediateMessagePrefix.length);
            const task = tasks[handle];
            if (task) {
                try {
                    task();
                } finally {
                    delete tasks[handle];
                };
            }
        }
    }

    globalThis.addEventListener("message", onGlobalMessage, false);
}

installPostMessageHandler();

function scheduleCallbackImmediate(callback: () => void) {
    if (IN_NODE) {
        // node has setImmediate, let's use it
        setImmediate(callback);
    } else if (IN_BROWSER_MAIN_THREAD) {
        // use postMessage
        tasks[nextTaskHandle] = callback;
        globalThis.postMessage(scheduleCallbackImmediateMessagePrefix + nextTaskHandle, "*");
        nextTaskHandle++;
    } else if (IN_BROWSER_WEB_WORKER) {
        // use MessageChannel
        const channel = new MessageChannel();
        channel.port1.onmessage = () => callback();
        channel.port2.postMessage(null);
    } else {
        // fallback to setTimeout
        setTimeout(callback, 0);
    }

}

/**
 * Schedule a callback. Supports both immediate and delayed callbacks.
 * @param callback The callback to be scheduled
 * @param timeout The delay in milliseconds before the callback is called
 */
export function scheduleCallback(callback: () => void, timeout: number = 0) {
  if (timeout < 4) {
    scheduleCallbackImmediate(callback);
  } else {
    setTimeout(callback, timeout);
  }
}
