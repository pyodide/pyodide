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
let cur_uuid;
rl.on("line", async function (line) {
    if (!cur_uuid) {
        // assert(len(line) == 36, "Was expecting a uuid");
        cur_uuid = line;
        console.log("received uuid", line);
        return;
    }
    if (line !== cur_uuid) {
        cur_code += line + "\n";
        console.log("added code", line);
    } else {
        console.log("evaling code", cur_code);
        evalCode(cur_uuid, cur_code, context);
        cur_code = "";
        cur_uuid = undefined;
    }
});

async function evalCode(uuid, code, eval_context) {
    let p = new Promise((resolve, reject) => {
        context.___outer_resolve = resolve;
        context.___outer_reject = reject;
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
