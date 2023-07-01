export {};
import type { Module as OrigModule } from "./module";

import { defines } from "./generated_struct_info32.gen.json";

export { defines as cDefs };

declare global {
  export const cDefs: typeof defines;
  // export const DEBUG = false;
  export const DEBUG: boolean;
  export var Module: OrigModule;
  export var API: any;
}
