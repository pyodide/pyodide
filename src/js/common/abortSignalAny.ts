/**
 * Polyfill for the static method `AbortSignal.any` which is not yet implemented
 * in all browsers. This function creates a new `AbortSignal` that is aborted
 * when any of the provided signals are aborted, which is used in `pyfetch`.
 *
 * @see https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/any_static#browser_compatibility
 *
 *    deno: 1.39   (Released 2023-12)
 *  nodejs: 20.3.0 (Released 2023-06)
 *  chrome: 100    (Released 2023-08)
 *  safari: 17.4   (Released 2024-03)
 * firefox: 124    (Released 2024-03)
 *
 * We may consider dropping this polyfill after EOL of Node.js 18 (April 2025).
 */

interface _AbortSignal extends AbortSignal {
      /** @private */
      __controller?: AbortController;
}

const registry = new FinalizationRegistry((callback: () => any) => void callback());

function abortSignalAny(signals: AbortSignal[]) {
      const controller = new AbortController();
      for (const signal of signals) {
            if (signal.aborted) {
                  controller.abort(signal.reason);
                  return controller.signal;
            }
      }
      const controllerRef = new WeakRef(controller);
      const eventListenerPairs: [WeakRef<AbortSignal>, () => void][] = [];
      let followingCount = signals.length;

      signals.forEach((signal) => {
            const signalRef = new WeakRef(signal);
            function abort() {
                  controllerRef.deref()?.abort(signalRef.deref()?.reason);
            }
            signal.addEventListener("abort", abort);
            eventListenerPairs.push([signalRef, abort]);
            registry.register(signal, () => !--followingCount && clear(), signal);
      });

      function clear() {
            eventListenerPairs.forEach(([signalRef, abort]) => {
                  const signal = signalRef.deref();
                  if (signal) {
                        signal.removeEventListener("abort", abort);
                        registry.unregister(signal);
                  }
                  const controller = controllerRef.deref();
                  if (controller) {
                        registry.unregister(controller.signal);
                        delete (controller.signal as _AbortSignal).__controller;
                  }
            });
      }

      const { signal }: { signal: _AbortSignal } = controller;

      registry.register(signal, clear, signal);
      signal.addEventListener("abort", clear);

      signal.__controller = controller; // keep a strong reference

      return signal;
}

export default abortSignalAny;
