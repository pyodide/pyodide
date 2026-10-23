// Conversion of containers between JS and Python.
//
//   toJs: PyProxy.toJs() on a Python container (python2js)
//   toPy: pyodide.toPy() on the equivalent JS container (js2python)
//
// The cases cover the per-element overhead of the conversion for common
// element types, so they are dominated by the work done per element rather
// than by the work done per call.

export const description =
  "toJs() / toPy() of lists and dicts of ints, floats, strings and records";

const N = 100_000;
const RECORDS = 20_000;
const ROWS = 1_000;
const COLS = 100;

const CASES = {
  int: {
    py: `list(range(${N}))`,
    js: () => Array.from({ length: N }, (_, i) => i),
  },
  float: {
    py: `[i + 0.5 for i in range(${N})]`,
    js: () => Array.from({ length: N }, (_, i) => i + 0.5),
  },
  str: {
    py: `[f"s{i % 1000}" for i in range(${N})]`,
    js: () => Array.from({ length: N }, (_, i) => `s${i % 1000}`),
  },
  mixed: {
    py: `[(i, i + 0.5, f"s{i % 1000}", None, True)[i % 5] for i in range(${N})]`,
    js: () =>
      Array.from(
        { length: N },
        (_, i) => [i, i + 0.5, `s${i % 1000}`, undefined, true][i % 5],
      ),
  },
  // A list of records, as typically produced by JSON
  records: {
    py: `[{"id": i, "name": f"n{i}", "score": i / 2, "ok": True, "tag": None} for i in range(${RECORDS})]`,
    js: () =>
      Array.from({ length: RECORDS }, (_, i) => ({
        id: i,
        name: `n${i}`,
        score: i / 2,
        ok: true,
        tag: undefined,
      })),
  },
  nested: {
    py: `[list(range(${COLS})) for _ in range(${ROWS})]`,
    js: () =>
      Array.from({ length: ROWS }, () =>
        Array.from({ length: COLS }, (_, i) => i),
      ),
  },
};

// Cheap structural check that both directions produce the expected value.
function check(pyodide, caseName, pyObj, jsObj) {
  pyodide.globals.set("converted", pyodide.toPy(jsObj));
  pyodide.globals.set("expected", pyObj);
  const ok = pyodide.runPython("converted == expected");
  pyodide.globals.delete("converted");
  pyodide.globals.delete("expected");
  if (!ok) {
    throw new Error(`toPy result mismatch: ${caseName}`);
  }
  const back = pyObj.toJs({ dict_converter: Object.fromEntries });
  if (JSON.stringify(back) !== JSON.stringify(jsObj)) {
    throw new Error(`toJs result mismatch: ${caseName}`);
  }
}

export async function run(pyodide, { filter, measure }) {
  const results = {};
  for (const [caseName, { py, js }] of Object.entries(CASES)) {
    if (!filter(caseName)) {
      continue;
    }
    const pyObj = pyodide.runPython(py);
    const jsObj = js();

    const toJs = await measure(() => pyObj.toJs());
    const toPy = await measure(() => pyodide.toPy(jsObj).destroy());

    check(pyodide, caseName, pyObj, jsObj);
    pyObj.destroy();
    results[caseName] = { toJs, toPy };
  }
  return results;
}
