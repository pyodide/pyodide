import type { Module as OrigModule } from "./module";
import { defines } from "./generated_struct_info32.json";

declare global {
  export const cDefs: typeof defines;
  export const DEBUG: boolean;
  export const SOURCEMAP: boolean;
  export var Module: OrigModule;
  export var API: any;
}
