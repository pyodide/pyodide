/**
 * Schedule a callback. Supports both immediate and delayed callbacks.
 * @param callback The callback to be scheduled
 * @param timeout The delay in milliseconds before the callback is called
 */
export function scheduleCallback(callback: () => void, timeout: number = 0) {
  // In modern browsers, setTimeout has throttling minimum delay (mostly 4ms).
  // So to support immediate callbacks, we use MessageChannel if the delay is less than 4ms.
  // Ref0: https://github.com/pyodide/pyodide/issues/4006
  // Ref1: (firefox) https://developer.mozilla.org/en-US/docs/Web/API/setTimeout
  // Ref2: (chrome) https://developer.chrome.com/blog/timer-throttling-in-chrome-88
  if (timeout < 4) {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => callback();
    channel.port2.postMessage("");
  } else {
    setTimeout(callback, timeout);
  }
}
