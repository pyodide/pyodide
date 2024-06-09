function polyfillAbortSignalAny() {
  /** @param {AbortSignal[]} signals */
  return (signals) => {
    if (AbortSignal.any) {
      return AbortSignal.any(signals);
    }
    const controller = new AbortController();
    const controllerRef = new WeakRef(controller);
    /** @type {[WeakRef<AbortSignal>, (() => void)][]} */
    const eventListenerPairs = [];
    let followingCount = signals.length;

    /** @type {FinalizationRegistry<(callback: () => any) => void>} */
    const registry = (globalThis.__abortSignalCleanups =
      globalThis.__abortSignalCleanups ??
      new FinalizationRegistry((callback) => void callback()));

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
          delete controller.signal.__controller;
        }
      });
    }

    const { signal } = controller;

    registry.register(signal, clear, signal);
    signal.addEventListener("abort", clear);

    signal.__controller = controller; // keep a strong reference

    return signal;
  };
}
