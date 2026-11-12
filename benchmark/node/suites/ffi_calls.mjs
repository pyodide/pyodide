// Overhead of calls and attribute access across the JS <-> Python boundary.
//
//   py2js_*: Python code operating on a JsProxy (the loop runs in Python)
//   js2py_*: JS code operating on a PyProxy (the loop runs in JS)
//
// Each case performs OPS operations, so the per-call overhead dominates.

export const description = "Calls and attribute access between JS and Python";

const OPS = 20_000;

export async function run(pyodide, { filter, measure }) {
  const results = {};

  // Python operating on JS objects
  const jsObj = {
    foo: 1,
    method(x) {
      return x;
    },
  };
  const jsFunc = (x) => x;
  pyodide.globals.set("js_obj", jsObj);
  pyodide.globals.set("js_func", jsFunc);
  const pyLoops = {
    py2js_getattr: `
def bench():
    o = js_obj
    for _ in range(${OPS}):
        o.foo
`,
    py2js_setattr: `
def bench():
    o = js_obj
    for _ in range(${OPS}):
        o.foo = 1
`,
    py2js_call: `
def bench():
    f = js_func
    for _ in range(${OPS}):
        f(1)
`,
    py2js_method_call: `
def bench():
    o = js_obj
    for _ in range(${OPS}):
        o.method(1)
`,
  };
  for (const [caseName, code] of Object.entries(pyLoops)) {
    if (!filter(caseName)) {
      continue;
    }
    pyodide.runPython(code);
    const bench = pyodide.globals.get("bench");
    results[caseName] = { time: await measure(() => bench()) };
    bench.destroy();
  }

  // JS operating on Python objects
  const [pyObj, pyFunc, pyFuncObj] = pyodide.runPython(`
class A:
    def __init__(self):
        self.foo = 1
    def method(self, x):
        return x

def py_func(x):
    return x

def py_func_obj():
    return A()

[A(), py_func, py_func_obj]
`);
  const jsLoops = {
    js2py_getattr: () => {
      for (let i = 0; i < OPS; i++) {
        pyObj.foo;
      }
    },
    js2py_call: () => {
      for (let i = 0; i < OPS; i++) {
        pyFunc(1);
      }
    },
    // The result is a PyProxy, which is destroyed right away.
    js2py_call_returning_object: () => {
      for (let i = 0; i < OPS; i++) {
        pyFuncObj().destroy();
      }
    },
    js2py_method_call: () => {
      for (let i = 0; i < OPS; i++) {
        pyObj.method(1);
      }
    },
  };
  for (const [caseName, loop] of Object.entries(jsLoops)) {
    if (!filter(caseName)) {
      continue;
    }
    results[caseName] = { time: await measure(loop) };
  }

  // Sanity checks
  if (pyObj.foo !== 1 || pyFunc(2) !== 2 || pyObj.method(3) !== 3) {
    throw new Error("Unexpected result from Python");
  }
  if (pyodide.runPython("js_obj.method(4) + js_func(5) + js_obj.foo") !== 10) {
    throw new Error("Unexpected result from JS");
  }
  pyObj.destroy();
  pyFunc.destroy();
  pyFuncObj.destroy();
  return results;
}
