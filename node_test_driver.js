const vm = require('vm');
const readline = require('readline');
const path = require('path');
var util = require('util');
require(path.resolve("./pyodide.js"));

for(let key of Object.keys(util.inspect.styles)){
    util.inspect.styles[key] = undefined;    
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});
const SEP = "\0x1E";
// const SEP = "A";


const context = { path, process, require, loadPyodide };
vm.createContext(context);
vm.runInContext("globalThis.self = globalThis;", context);



let cur_code = "";
rl.on('line', async function(line){
    if(line === SEP){
        let p = new Promise((resolve, reject) => {
            context.___outer_resolve = resolve;
            context.___outer_reject = reject;
        });
        let code = `
        (async function(){
            ${cur_code}
        })().then(___outer_resolve).catch(___outer_reject);
        `
        try {
            vm.runInContext(code, context);
            let result = JSON.stringify(await p);
            console.log(0);
            console.log(result);
            console.log(SEP);
        } catch(e){
            console.log(1);
            console.log(e.stack);
            console.log(SEP);
        }
        cur_code = "";
    } else {
        cur_code += line + "\n";
    }
})
