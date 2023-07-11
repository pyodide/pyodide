/**
 *
 */

import { build } from "esbuild";
import { readFileSync } from "node:fs";
import loadWabt from "../../js/node_modules/wabt/index.js";
import { dirname, join } from "node:path";

const __dirname = dirname(new URL(import.meta.url).pathname);

const { parseWat } = await loadWabt();

/**
 * An esbuild plugin that imports wat files.
 *
 * It
 */
function watPlugin() {
  return {
    name: "watPlugin",
    setup(build) {
      build.onLoad({ filter: /.wat$/ }, async (args) => {
        const wasmModule = parseWat(
          args.path,
          readFileSync(args.path, { encoding: "utf8" }),
        );
        const contents = wasmModule.toBinary({}).buffer;
        return {
          contents,
          loader: "binary",
        };
      });
    },
  };
}

const outfile = join(__dirname, "continuations.out.js");
const globalName = "Continuations";

const config = {
  entryPoints: [join(__dirname, "continuations.mjs")],
  outfile,
  format: "iife",
  bundle: true,
  plugins: [watPlugin()],
  globalName,
  metafile: true,
};

const { metafile } = await build(
  Object.assign({}, config, { format: "esm", bundle: false }),
);
const exports = Object.entries(metafile.outputs)[0][1].exports;
const footer = `
  const {${exports}} = Continuations;
  Object.assign(Module, Continuations);
`.replaceAll(/\s/g, "");

config.footer = { js: footer };
await build(config);
