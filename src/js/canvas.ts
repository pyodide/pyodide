declare var Module: any;

/**
 * This interface contains the helper functions for using the HTML5 canvas.
 *
 * As of now, Emscripten uses Module.canvas to get the canvas element.
 * This might change in the future, so we abstract it here.
 * @hidden
 */
export interface CanvasInterface {
  setCanvas2D(canvas: HTMLCanvasElement): void;
  getCanvas2D(): HTMLCanvasElement | undefined;
  setCanvas3D(canvas: HTMLCanvasElement): void;
  getCanvas3D(): HTMLCanvasElement | undefined;
}

// We define methods here to make sphinx-js generate documentation for them.

/**
 * Set the HTML5 canvas element to use for 2D rendering. For now,
 * Emscripten only supports one canvas element, so setCanvas2D and setCanvas3D
 * are the same.
 */
export const setCanvas2D = (canvas: HTMLCanvasElement) => {
  if (canvas.id !== "canvas") {
    console.warn(
      "If you are using canvas element for SDL library, it should have id 'canvas' to work properly.",
    );
  }

  Module.canvas = canvas;
};
/**
 * Get the HTML5 canvas element used for 2D rendering. For now,
 * Emscripten only supports one canvas element, so getCanvas2D and getCanvas3D
 * are the same.
 */
export const getCanvas2D = (): HTMLCanvasElement | undefined => {
  return Module.canvas;
};
/**
 * Set the HTML5 canvas element to use for 3D rendering. For now,
 * Emscripten only supports one canvas element, so setCanvas2D and setCanvas3D
 * are the same.
 */
export const setCanvas3D = (canvas: HTMLCanvasElement) => {
  setCanvas2D(canvas);
};
/**
 * Get the HTML5 canvas element used for 3D rendering. For now,
 * Emscripten only supports one canvas element, so getCanvas2D and getCanvas3D
 * are the same.
 */
export const getCanvas3D = (): HTMLCanvasElement | undefined => {
  return getCanvas2D();
};

/**
 * @private
 */
export const canvas: CanvasInterface = {
  setCanvas2D,
  getCanvas2D,
  setCanvas3D,
  getCanvas3D,
};
