const vm = require("vm");
const readline = require("readline");
const path = require("path");
const util = require("util");
const node_fetch = require("node-fetch");

require(path.resolve("./pyodide.js"));
let base_url = process.argv[2];
// node requires full paths.
function fetch(path) {
  return node_fetch(new URL(path, base_url).toString());
}

const context = Object.assign({}, globalThis, {
  path,
  process,
  require,
  fetch,
  TextDecoder: util.TextDecoder,
  TextEncoder: util.TextEncoder,
  URL,
});
vm.createContext(context);
vm.runInContext("globalThis.self = globalThis;", context);

// Get rid of all colors in output of console.log, they mess us up.
for (let key of Object.keys(util.inspect.styles)) {
  util.inspect.styles[key] = undefined;
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});
const SEP = "\x1E";

let cur_code = "";
rl.on("line", async function (line) {
  if (line === SEP) {
    let p = new Promise((resolve, reject) => {
      context.___outer_resolve = resolve;
      context.___outer_reject = reject;
    });
    let code = `
        (async function(){
            ${cur_code}
        })().then(___outer_resolve).catch(___outer_reject);
        `;
    try {
      vm.runInContext(code, context);
      let result = JSON.stringify(await p);
      console.log(SEP + "0");
      console.log(result);
      console.log(SEP);
    } catch (e) {
      console.log(SEP + "1");
      console.log(e.stack);
      console.log(SEP);
    }
    cur_code = "";
  } else {
    cur_code += line + "\n";
  }
});
