import { Module } from "./module";

/**
 * @private
 * This interface contains the helper functions for SDL.
 */
export interface SDL {
  setCanvas2D(canvas: HTMLCanvasElement): void;
  getCanvas2D(): HTMLCanvasElement | undefined;
  setCanvas3D(canvas: HTMLCanvasElement): void;
  getCanvas3D(): HTMLCanvasElement | undefined;
}

/** @private */
export function registerSDL(Module: Module): SDL {
  function setCanvas2D(canvas: HTMLCanvasElement) {
    Module.canvas = canvas;
  }

  function setCanvas3D(canvas: HTMLCanvasElement) {
    Module.canvas = canvas;
  }

  function getCanvas2D(): HTMLCanvasElement | undefined {
    return Module.canvas;
  }

  function getCanvas3D(): HTMLCanvasElement | undefined {
    return Module.canvas;
  }

  return {
    setCanvas2D,
    setCanvas3D,
    getCanvas2D,
    getCanvas3D,
  };
}
