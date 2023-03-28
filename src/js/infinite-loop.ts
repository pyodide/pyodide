declare var Module: any;
declare var DEBUG: boolean;

/**
 * Checks if the program is running an main loop
 * @returns {boolean}
 */
export function running(): boolean {
  return !Module.Browser.mainLoop.func === null;
}

/**
 * Cancel the running main loop
 */
export function cancel(): void {
  if (!running()) {
    if (DEBUG) {
      console.log("[DEBUG] No running main loop");
    }
  }

  Module._emscripten_cancel_main_loop();
}

/**
 * Save the current thread state
 */
export function saveThreadState(): void {
  if (Module._is_thread_state_saved()) {
    if (DEBUG) {
      console.debug("[DEBUG] Thread state already saved");
    }
    return;
  }

  Module._save_current_thread_state();
}

/**
 * Restore the thread state
 */
export function restoreThreadState(): void {
  if (!Module._is_thread_state_saved()) {
    if (DEBUG) {
      console.debug("[DEBUG] Thread state not saved");
    }
    return;
  }

  Module._restore_thread_state();
}

/**
 * @private
 */
export interface PyodideLoopInterface {
  running: () => boolean;
  cancel: () => void;
  saveThreadState: () => void;
  restoreThreadState: () => void;
}

/**
 * @private
 */
export const loop: PyodideLoopInterface = {
  running,
  cancel,
  saveThreadState,
  restoreThreadState,
};
