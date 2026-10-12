import { defines } from "./generated_struct_info32.json";

declare global {
  /** @private */
  export const cDefs: typeof defines;
  /** @private */
  export const DEBUG: boolean;
  /** @private */
  export const SOURCEMAP: boolean;
  /** The Pyodide version, injected at build time from PYODIDE_VERSION. */
  export const API_VERSION: string;
  /** The Pyodide ABI version, injected at build time from PYODIDE_ABI_VERSION. */
  export const ABI_VERSION: string;
}

/** @hidden */
export const unpackArchiveMetadata = new Map([
  ["INSTALLER", "pyodide.unpackArchive"],
]);
