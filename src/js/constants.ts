import { defines } from "./generated_struct_info32.json";

declare global {
	/** @private */
	export const cDefs: typeof defines;
	/** @private */
	export const DEBUG: boolean;
	/** @private */
	export const SOURCEMAP: boolean;
}

/** @hidden */
export const unpackArchiveMetadata = new Map([
	["INSTALLER", "pyodide.unpackArchive"],
]);
