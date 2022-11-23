const fs = require("fs");
const { execFileSync } = require("child_process");

process.argv[2].split();

const path = process.argv[2].split("/");
const filename = path.pop().split(".")[0];
process.chdir(path.join("/"));

try {
    execFileSync("wat2wasms", [filename + ".wat", "--enable-all"]);
} catch (e) {
    if (e.code === "ENOENT") {
        process.stderr.write(
            "assemble_wat.js: wat2wasm is not on path. " +
                "Please install the WebAssembly Binary Toolkit.\n",
        );
        process.stderr.write("Quitting.\n");
        process.exit(1);
    }
    throw e;
}

const f = fs.readFileSync(filename + ".wasm");
fs.unlinkSync(filename + ".wasm");

const s = Array.from(f, (x) => x.toString(16).padStart(2, "0")).join("");
const output = `const ${filename}_wasm = decodeHexString("${s}");`;
fs.writeFileSync(filename + ".wasm.gen.js", output);
