const fs = require("fs");
const { execFileSync } = require("child_process");

process.argv[2].split();

const path = process.argv[2].split("/");
const filename = path.pop().split(".")[0];
process.chdir(path.join("/"));

execFileSync("wat2wasm", [filename + ".wat", "--enable-all"]);

const f = fs.readFileSync(filename + ".wasm");
fs.unlinkSync(filename + ".wasm");

const s = Array.from(f, (x) => x.toString(16).padStart(2, "0")).join("");
const output = `const ${filename}_wasm = decodeHexString("${s}");`;
fs.writeFileSync(filename + ".wasm.gen.js", output);
