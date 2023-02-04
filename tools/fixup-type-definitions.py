"""
This file ensures that only types are exported from the .d.ts files, not as
values. dts-bundle-generator seems to mess this up: things that were only
exported as types from `ffi.d.ts` get exported as values here.

It also adds deprecation notices to the type exports from pyodide.d.ts that
would otherwise be missing them.
"""

import re
from pathlib import Path


def main(filename):
    exported_things = set()
    path = Path(filename)
    text = path.read_text()
    exported_things.update(
        x.group(1) for x in re.finditer("export interface ([A-Za-z]*)", text)
    )
    exported_things.update(
        x.group(1) for x in re.finditer("export declare class ([A-Za-z]*)", text)
    )

    if path.name == "pyodide.d.ts":
        deprecated = r'\n/** @deprecated Use `import type { \2 } from "pyodide/ffi"` instead */\g<0>'
        text = re.sub(r"\n(export )?interface (Py[A-Za-z]*).*", deprecated, text)
        text = re.sub(r"\n(declare class) (PyBufferView)", deprecated, text)
        text = re.sub(r"\n(export type) (TypedArray)", deprecated, text)
        text = text.replace("export type ConfigType", "type ConfigType")
    if path.name == "ffi.d.ts":
        text = text.replace("export declare const ffi", "declare const ffi")

    text = text.replace("export interface", "interface")
    text = text.replace("export declare class", "declare class")
    text = text.replace("export {", "export type {")
    type_exports = ", ".join(sorted(exported_things))
    text += f"export type {{{type_exports}}};\n"
    path.write_text(text)


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1]))
