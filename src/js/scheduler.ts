/**
 * Schedule a callback. Supports both immediate and delayed callbacks.
 * @param callback The callback to be scheduled
 * @param timeout The delay in milliseconds before the callback is called
 */
export function scheduleCallback(callback: () => void, timeout: number = 0) {
  if (timeout <= 0) {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => callback();
    channel.port2.postMessage("");
  } else {
    setTimeout(callback, timeout);
  }
}
