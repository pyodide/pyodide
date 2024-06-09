const registry = new FinalizationRegistry(
  (callback: () => any) => void callback(),
);

interface _AbortSignal extends AbortSignal {
  /** @private */
  __controller?: AbortController;
}

API.abortSignalAny =
  // @ts-ignore
  AbortSignal.any ??
  function (signals: AbortSignal[]) {
    const controller = new AbortController();
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
  };
