// JS <-> Python string conversion.
//
//   py2js: PyProxy.toJs() on a Python list of strings (python2js_unicode)
//   js2py: pyodide.toPy() on a JS array of strings (js2python_string)
//
// over several string kinds and lengths. Each case converts TOTAL_CHARS
// characters in total. Also checks that the conversions are lossless.

export const description =
  "JS <-> Python string conversion for ascii/latin1/ucs2/ucs4 strings";

const TOTAL_CHARS = 1 << 21;
const LENGTHS = [8, 64, 1024, 65536];
const KINDS = {
  ascii: "abcdefghijklmnopqrstuvwxyz0123456789",
  latin1: "abcdé\x80\x9f\xff",
  ucs2: "abc한글テスト中",
  ucs4: "ab한\u{1F600}\u{1F680}",
};

function makeString(alphabet, len, seed) {
  const chars = Array.from(alphabet);
  let out = "";
  for (let i = 0; out.length < len; i++) {
    out += chars[(i * 7 + seed) % chars.length];
  }
  // Keep surrogate pairs intact when trimming
  return Array.from(out).slice(0, len).join("");
}

function checkEdgeCases(pyodide) {
  // Lone surrogates and boundaries between the 1-, 2- and 4-byte kinds
  const edge = [
    "",
    "\ud800",
    "a\udc00b",
    "\ud83d",
    "x😀\ud800",
    "\xffĀ",
    "￿\u{10000}",
    "\u{10FFFF}",
  ];
  const expected = [
    [],
    [0xd800],
    [0x61, 0xdc00, 0x62],
    [0xd83d],
    [0x78, 0x1f600, 0xd800],
    [0xff, 0x100],
    [0xffff, 0x10000],
    [0x10ffff],
  ];
  pyodide.globals.set("edge", pyodide.toPy(edge));
  const codepoints = pyodide
    .runPython("[[ord(c) for c in s] for s in edge]")
    .toJs();
  if (JSON.stringify(codepoints) !== JSON.stringify(expected)) {
    throw new Error(`js2py edge case mismatch: ${JSON.stringify(codepoints)}`);
  }
  const edgeBack = pyodide.runPython("edge").toJs();
  if (JSON.stringify(edgeBack) !== JSON.stringify(edge)) {
    throw new Error("py2js edge case mismatch");
  }
}

export async function run(pyodide, { filter, measure }) {
  const results = {};
  for (const [kind, alphabet] of Object.entries(KINDS)) {
    for (const len of LENGTHS) {
      const caseName = `${kind}/${len}`;
      if (!filter(caseName)) {
        continue;
      }
      const count = Math.max(1, Math.floor(TOTAL_CHARS / len));
      const jsStrings = [];
      for (let i = 0; i < count; i++) {
        jsStrings.push(makeString(alphabet, len, i));
      }

      // Build Python-side strings independently of the code under test.
      pyodide.globals.set("alphabet", alphabet);
      const pyList = pyodide.runPython(`
        chars = list(alphabet)
        def make(n, seed):
            out = []
            i = 0
            while len(out) < n:
                out.append(chars[(i * 7 + seed) % len(chars)])
                i += 1
            return "".join(out)
        [make(${len}, i) for i in range(${count})]
      `);

      const py2js = await measure(() => pyList.toJs());
      const js2py = await measure(() => pyodide.toPy(jsStrings).destroy());

      // Round trip must be lossless
      const back = pyodide.toPy(jsStrings).toJs();
      for (let i = 0; i < count; i++) {
        if (back[i] !== jsStrings[i]) {
          throw new Error(`round trip mismatch: ${caseName} i=${i}`);
        }
      }
      pyList.destroy();
      results[caseName] = { py2js, js2py };
    }
  }
  // Run this last so that it doesn't affect the JIT state for the timings.
  checkEdgeCases(pyodide);
  return results;
}
