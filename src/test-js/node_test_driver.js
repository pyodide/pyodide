const vm = require("vm");
const readline = require("readline");
const path = require("path");
const util = require("util");
const node_fetch = require("node-fetch");
const base64 = require("base-64");

let { loadPyodide } = require("pyodide");
let base_url = process.argv[2];
// node requires full paths.
function fetch(path) {
  return node_fetch(new URL(path, base_url).toString());
}

const context = {
  loadPyodide,
  path,
  process,
  require,
  fetch,
  setTimeout,
  TextDecoder: util.TextDecoder,
  TextEncoder: util.TextEncoder,
  URL,
  atob: base64.decode,
  btoa: base64.encode,
};
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

let cur_code = "";
let cur_uuid;
rl.on("line", async function (line) {
  if (!cur_uuid) {
    cur_uuid = line;
    return;
  }
  if (line !== cur_uuid) {
    cur_code += line + "\n";
  } else {
    evalCode(cur_uuid, cur_code, context);
    cur_code = "";
    cur_uuid = undefined;
  }
});

async function evalCode(uuid, code, eval_context) {
  let p = new Promise((resolve, reject) => {
    eval_context.___outer_resolve = resolve;
    eval_context.___outer_reject = reject;
  });
  let wrapped_code = `
      (async function(){
          ${code}
      })().then(___outer_resolve).catch(___outer_reject);
      `;
  let delim = uuid + ":UUID";
  console.log(delim);
  try {
    vm.runInContext(wrapped_code, eval_context);
    let result = JSON.stringify(await p);
    console.log(`${delim}\n0\n${result}\n${delim}`);
  } catch (e) {
    console.log(`${delim}\n1\n${e.stack}\n${delim}`);
  }
}
console.log("READY!!");
// evalCode("xxx", "let pyodide = await loadPyodide(); pyodide.runPython(`print([x*x+1 for x in range(10)])`);", context);
