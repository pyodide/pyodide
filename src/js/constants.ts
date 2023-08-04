import type { Module as OrigModule } from "./module";
import { defines } from "./generated_struct_info32.gen.json";

declare global {
  export const cDefs: typeof defines;
  export const DEBUG: boolean;
  export var Module: OrigModule;
  export var API: any;
}
