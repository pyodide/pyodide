import { Module } from "./module";

/**
 * @private
 * This interface contains the helper functions for SDL.
 */
export interface SDL {
  setCanvas(canvas: HTMLElement): void;
  unsetCanvas(): void;
  getCanvas(): HTMLElement | undefined;
}

/** @private */
export function registerSDL(Module: Module): SDL {
  function setCanvas(canvas: HTMLElement) {
    Module.canvas = canvas;
  }

  function unsetCanvas() {
    Module.canvas = undefined;
  }

  function getCanvas(): HTMLElement | undefined {
    return Module.canvas;
  }

  return {
    setCanvas,
    unsetCanvas,
    getCanvas,
  };
}
