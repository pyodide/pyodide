declare var Module: any;
declare var DEBUG: boolean;

/**
 * Checks if the program is running an infinite loop
 * @returns {boolean}
 */
export function is_running_infinite_loop(): boolean {
  return Module.Browser.mainLoop.func === null;
}

/**
 * Cancel the running infinite loop
 */
export function cancel_infinite_loop(): void {
  if (!is_running_infinite_loop()) {
    if (DEBUG) {
      console.log("[DEBUG] No running infinite loop");
    }
  }

  Module._emscripten_cancel_main_loop();
}
