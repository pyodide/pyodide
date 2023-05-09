/**
 * Resolve WAT imports in continuation.js and wrap in EM_JS to define
 * continuations_init_js
 */

import { readFileSync, writeFileSync } from "node:fs";
import loadWabt from "../js/node_modules/wabt/index.js";
import { join } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

const import_re = /import ([{A-Za-z0-9_},]*) from "([A-Za-z0-9_/.]*)";\n/gm;
const identifier_re = /^[A-Za-z0-9_$]*$/;

/**
 * Convert buffer to a hexadecimal string.
 *
 * It's not quite as dense as base 64 encoding, but faster to encode/decode.
 * Note that these buffers are not all that large (~200 bytes)
 */
function toHexString(buffer) {
  return Array.from(buffer, (x) => x.toString(16).padStart(2, "0")).join("");
}

const parseWatPromise = loadWabt().then(({ parseWat }) => parseWat);

/**
 * Resolve wat imports as Uint8Arrays.
 * @param input The input JavaScript source string
 * @returns The same JavaScript code with the wat imports fixed up.
 */
async function handleWatImports(input) {
  const parseWat = await parseWatPromise;
  return input.replaceAll(import_re, function (orig, name, file) {
    if (!file.endsWith(".wat")) {
      // Only handle .wat imports
      return orig;
    }
    if (!identifier_re.test(name)) {
      throw new Error(`Can only handle "import identifier from '*.wat';"`);
    }
    const wasmModule = parseWat(
      name,
      readFileSync(join(__dirname, file), { encoding: "utf8" }),
    );
    const wasmBinary = wasmModule.toBinary({}).buffer;
    const hexString = toHexString(wasmBinary);
    return `const ${name} = decodeHexString("${hexString}");\n`;
  });
}

/**
 * Resolve wat imports and wrap in EM_JS, then write to continuations.gen.js
 */
async function buildContinuations() {
  const input = readFileSync(join(__dirname, "./continuations.js"), {
    encoding: "utf8",
  });
  const output = await handleWatImports(input);
  const emjs_wrapped_output = [
    "#include <emscripten.h>",
    "EM_JS(int, continuations_init_js, (), {",
    output,
    "});",
  ];
  writeFileSync(
    join(__dirname, "./continuations.gen.js"),
    emjs_wrapped_output.join("\n"),
  );
}

buildContinuations();
