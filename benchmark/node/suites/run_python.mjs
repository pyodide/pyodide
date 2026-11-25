// Per-call overhead of running Python code from JavaScript.
//
//   run_python_expr:      runPython("1 + 1"): the last statement is an
//                         expression, so its value is returned
//   run_python_stmt:      runPython("x = 1"): nothing is returned
//   run_python_semicolon: runPython("1 + 1;"): a trailing semicolon
//                         suppresses the result
//   run_python_large:     runPython on about 480 lines of function
//                         definitions; parsing and compiling dominate
//   run_python_async:     runPythonAsync("1 + 1")
//
// The code is tiny (except for run_python_large), so the cost is mostly the
// work runPython does around it: parsing, rewriting the last statement and
// compiling.

export const description = "Overhead of runPython and runPythonAsync";

const OPS = 2_000;
const ASYNC_OPS = 1_000;
const LARGE_OPS = 20;

const LARGE_SOURCE =
  Array.from(
    { length: 120 },
    (_, i) =>
      `def f${i}(a, b):\n    c = a + b * ${i}\n    return [c, {"k": c}, (a, b)]\n`,
  ).join("\n") + "\nf1(1, 2)";

export async function run(pyodide, { filter, measure }) {
  const results = {};
  const globals = pyodide.toPy({});
  const options = { globals };

  // Check the results once, so that a broken build doesn't report timings.
  const expected = [
    ["1 + 1", 2],
    ["x = 1", undefined],
    ["1 + 1;", undefined],
  ];
  for (const [code, value] of expected) {
    const result = pyodide.runPython(code, options);
    if (result !== value) {
      throw new Error(`runPython(${JSON.stringify(code)}) returned ${result}`);
    }
  }
  const largeResult = pyodide.runPython(LARGE_SOURCE, options);
  if (largeResult.toJs({ dict_converter: Object.fromEntries })[0] !== 3) {
    throw new Error("Unexpected result from the large source");
  }
  largeResult.destroy();
  if ((await pyodide.runPythonAsync("1 + 1", options)) !== 2) {
    throw new Error("Unexpected result from runPythonAsync");
  }

  const syncCases = {
    run_python_expr: ["1 + 1", OPS],
    run_python_stmt: ["x = 1", OPS],
    run_python_semicolon: ["1 + 1;", OPS],
    run_python_large: [LARGE_SOURCE, LARGE_OPS],
  };
  for (const [caseName, [code, ops]] of Object.entries(syncCases)) {
    if (!filter(caseName)) {
      continue;
    }
    results[caseName] = {
      time: await measure(() => {
        for (let i = 0; i < ops; i++) {
          const result = pyodide.runPython(code, options);
          if (result && result.destroy) {
            result.destroy();
          }
        }
      }),
    };
  }

  if (filter("run_python_async")) {
    results.run_python_async = {
      time: await measure(async () => {
        for (let i = 0; i < ASYNC_OPS; i++) {
          await pyodide.runPythonAsync("1 + 1", options);
        }
      }),
    };
  }

  globals.destroy();
  return results;
}
