import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { zipSync, strToU8 } from "fflate";
import { unpackZip } from "../../package-loading/archive.ts";

const enc = new TextEncoder();

describe("unpackZip", () => {
  it("unpacks stored and deflated entries with nested paths", () => {
    const soData = new Uint8Array([0, 97, 115, 109, 1, 2, 3, 4]);
    const zip = zipSync({
      "pkg/__init__.py": [strToU8("x = 1\n"), { level: 0 }],
      "pkg/mod.cpython-314-wasm32-emscripten.so": [soData, { level: 6 }],
      "pkg-1.0.dist-info/METADATA": [strToU8("Name: pkg\n"), { level: 6 }],
    });

    const entries = unpackZip(zip);
    const byName = new Map(entries.map((e) => [e.name, e.data]));

    assert.deepEqual(byName.get("pkg/__init__.py"), enc.encode("x = 1\n"));
    assert.deepEqual(
      byName.get("pkg/mod.cpython-314-wasm32-emscripten.so"),
      soData,
    );
    assert.deepEqual(
      byName.get("pkg-1.0.dist-info/METADATA"),
      enc.encode("Name: pkg\n"),
    );
  });

  it("round-trips arbitrary binary content", () => {
    const data = new Uint8Array(1024);
    for (let i = 0; i < data.length; i++) {
      data[i] = (i * 31) % 256;
    }
    const zip = zipSync({ "blob.bin": data });
    const entries = unpackZip(zip);
    assert.equal(entries.length, 1);
    assert.equal(entries[0].name, "blob.bin");
    assert.deepEqual(entries[0].data, data);
  });

  it("throws on invalid zip data", () => {
    assert.throws(() => unpackZip(new Uint8Array([1, 2, 3, 4])));
  });
});
