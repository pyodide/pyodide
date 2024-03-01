/**
 * Schedule a callback. Supports both immediate and delayed callbacks.
 * @param callback The callback to be scheduled
 * @param timeout The delay in milliseconds before the callback is called
 */

type MessageChannelWithCallback = MessageChannel & { _callback?: () => void };

const messageChannelsQueue: MessageChannelWithCallback[] = [];

function schduleCallbackImmediate(callback: () => void) {
  let channel = messageChannelsQueue.pop();
  if (channel === undefined) {
    channel = new MessageChannel();
    channel.port1.onmessage = () => {
      try {
        channel?._callback?.();
      } finally {
        messageChannelsQueue.push(channel!);
      }
    };
  }

  channel._callback = callback;
  channel.port2.postMessage("");
}


export function scheduleCallback(callback: () => void, timeout: number = 0) {
  // In modern browsers, setTimeout has throttling minimum delay (mostly 4ms).
  // So to support immediate callbacks, we use MessageChannel if the delay is less than 4ms.
  // Ref0: https://github.com/pyodide/pyodide/issues/4006
  // Ref1: (firefox) https://developer.mozilla.org/en-US/docs/Web/API/setTimeout
  // Ref2: (chrome) https://developer.chrome.com/blog/timer-throttling-in-chrome-88

  if (timeout < 4) {
    schduleCallbackImmediate(callback)
  } else {
    setTimeout(callback, timeout);
  }
}
