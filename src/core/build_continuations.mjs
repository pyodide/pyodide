import { readFileSync, writeFileSync } from "node:fs";
import loadWabt from "../js/node_modules/wabt/index.js";
import { join } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

const import_re = /import ([{A-Za-z0-9_},]*) from "([A-Za-z0-9_/.]*)";\n/gm;
const identifier_re = /^[A-Za-z0-9_$]*$/;

function toHexString(binary) {
  return Array.from(binary, (x) => x.toString(16).padStart(2, "0")).join("");
}

const parseWatPromise = loadWabt().then(({ parseWat }) => parseWat);

async function handleWatImports(input) {
  const parseWat = await parseWatPromise;

  return input.replaceAll(import_re, function (_, name, file) {
    if (!file.endsWith(".wat")) {
      throw new Error("Only can handle .wat imports");
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

async function buildContinuations() {
  const input = readFileSync(join(__dirname, "./continuations.js"), {
    encoding: "utf8",
  });
  const output = await handleWatImports(input);
  const emjs_wrapped_output = [
    "#include <emscripten.h>",
    '#include "hiwire.h"',
    "EM_JS(JsRef, hiwire_syncify, (JsRef idpromise), {",
    `throw new Error("Syncify not supported");`,
    "}",
    "{",
    output,
    "});",
  ];
  writeFileSync(
    join(__dirname, "./continuations.gen.js.c"),
    emjs_wrapped_output.join("\n"),
  );
}

buildContinuations();
