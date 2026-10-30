// Cost of exceptions crossing the JS <-> Python boundary.
//
//   py_catches_js_error: Python calls a JS function that throws and catches
//                        the JsException (the loop runs in Python)
//   js_catches_py_error: JS calls a Python function that raises and catches
//                        the PythonError (the loop runs in JS)
//   py_error_through_js: Python calls JS, which calls back into Python, which
//                        raises. The error passes through JS back to Python.
//   js_error_through_py: JS calls Python, which calls back into JS, which
//                        throws. The error passes through Python back to JS,
//                        where it arrives as a PythonError (for a JsException).
//
// Each case raises OPS exceptions.

export const description = "Exceptions crossing between JS and Python";

const OPS = 2_000;

export async function run(pyodide, { filter, measure }) {
  const results = {};

  // A Python function that raises, and a proxy of it that JS can call back
  const pyRaise = pyodide.runPython(`
def py_raise():
    raise ValueError("boom")
py_raise
`);
  const jsThrow = () => {
    throw new TypeError("boom");
  };
  const jsCallPyRaise = () => pyRaise();
  let pyCallJsThrow;

  pyodide.globals.set("js_throw", jsThrow);
  pyodide.globals.set("js_call_py_raise", jsCallPyRaise);
  pyodide.runPython(`
from pyodide.ffi import JsException

def py_catches_js_error():
    f = js_throw
    for _ in range(${OPS}):
        try:
            f()
        except JsException:
            pass

def py_error_through_js():
    f = js_call_py_raise
    for _ in range(${OPS}):
        try:
            f()
        except ValueError:
            pass

def py_call_js_throw():
    js_throw()
`);
  pyCallJsThrow = pyodide.globals.get("py_call_js_throw");

  const pyLoops = ["py_catches_js_error", "py_error_through_js"];
  for (const caseName of pyLoops) {
    if (!filter(caseName)) {
      continue;
    }
    const bench = pyodide.globals.get(caseName);
    results[caseName] = { time: await measure(() => bench()) };
    bench.destroy();
  }

  const { PythonError } = pyodide.ffi;
  const jsLoops = {
    js_catches_py_error: () => {
      for (let i = 0; i < OPS; i++) {
        try {
          pyRaise();
        } catch (e) {
          if (!(e instanceof PythonError)) {
            throw e;
          }
        }
      }
    },
    js_error_through_py: () => {
      for (let i = 0; i < OPS; i++) {
        try {
          pyCallJsThrow();
        } catch (e) {
          if (!(e instanceof PythonError)) {
            throw e;
          }
        }
      }
    },
  };
  for (const [caseName, loop] of Object.entries(jsLoops)) {
    if (!filter(caseName)) {
      continue;
    }
    results[caseName] = { time: await measure(loop) };
  }

  // Check that the exceptions arrive with the expected type
  try {
    pyRaise();
    throw new Error("Expected a PythonError");
  } catch (e) {
    if (!(e instanceof PythonError) || e.type !== "ValueError") {
      throw e;
    }
  }
  try {
    pyCallJsThrow();
    throw new Error("Expected a PythonError");
  } catch (e) {
    if (!(e instanceof PythonError) || e.type !== "JsException") {
      throw e;
    }
  }
  const caught = pyodide.runPython(`
caught = []
try:
    js_throw()
except JsException as e:
    caught.append(type(e).__name__)
try:
    js_call_py_raise()
except ValueError as e:
    caught.append(str(e))
caught
`);
  const caughtJs = caught.toJs();
  caught.destroy();
  if (JSON.stringify(caughtJs) !== JSON.stringify(["JsException", "boom"])) {
    throw new Error(`Unexpected exceptions in Python: ${caughtJs}`);
  }

  pyRaise.destroy();
  pyCallJsThrow.destroy();
  return results;
}
