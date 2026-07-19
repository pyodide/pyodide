import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { zipSync, strToU8, unzipSync } from "fflate";
import {
  unpackZip,
  unpackTar,
  unpackArchive,
} from "../../package-loading/archive.ts";

const enc = new TextEncoder();

function tarHeader(
  name: string,
  size: number,
  typeflag = "0",
  prefix = "",
): Uint8Array {
  const h = new Uint8Array(512);
  const put = (str: string, off: number) => h.set(enc.encode(str), off);
  put(name, 0);
  put("0000644\0", 100);
  put("0000000\0", 108);
  put("0000000\0", 116);
  put(size.toString(8).padStart(11, "0") + "\0", 124);
  put("00000000000\0", 136);
  for (let i = 148; i < 156; i++) h[i] = 0x20;
  h[156] = typeflag.charCodeAt(0);
  put("ustar\0", 257);
  put("00", 263);
  put(prefix, 345);
  let sum = 0;
  for (let i = 0; i < 512; i++) sum += h[i];
  put(sum.toString(8).padStart(6, "0") + "\0 ", 148);
  return h;
}

function makeTar(
  files: { name: string; data?: Uint8Array; typeflag?: string; prefix?: string }[],
): Uint8Array {
  const blocks: Uint8Array[] = [];
  for (const f of files) {
    const data = f.data ?? new Uint8Array(0);
    blocks.push(tarHeader(f.name, data.length, f.typeflag ?? "0", f.prefix));
    const padded = new Uint8Array(Math.ceil(data.length / 512) * 512);
    padded.set(data);
    blocks.push(padded);
  }
  blocks.push(new Uint8Array(1024));
  const total = blocks.reduce((n, b) => n + b.length, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const b of blocks) {
    out.set(b, o);
    o += b.length;
  }
  return out;
}

function paxRecord(key: string, value: string): string {
  const rest = ` ${key}=${value}\n`;
  let len = rest.length;
  for (;;) {
    const candidate = String(len).length + rest.length;
    if (candidate === len) break;
    len = candidate;
  }
  return String(len) + rest;
}

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

describe("unpackZip with a real wheel", () => {
  const distDir = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../../../../dist",
  );

  it("unpacks a built wheel and finds its dist-info METADATA", (t) => {
    if (!existsSync(distDir)) {
      t.skip("dist/ not built");
      return;
    }
    const wheel = readdirSync(distDir).find((f) => f.endsWith(".whl"));
    if (!wheel) {
      t.skip("no wheel in dist/");
      return;
    }

    const buffer = new Uint8Array(readFileSync(resolve(distDir, wheel)));
    const entries = unpackZip(buffer);

    const metadata = entries.find((e) =>
      /\.dist-info\/METADATA$/.test(e.name),
    );
    assert.ok(metadata, `no dist-info/METADATA found in ${wheel}`);
    assert.match(new TextDecoder().decode(metadata!.data), /^Metadata-Version:/m);

    const reference = unzipSync(buffer);
    assert.equal(entries.length, Object.keys(reference).length);
  });
});

describe("unpackTar", () => {
  it("unpacks files, nested paths, and directory entries", () => {
    const tar = makeTar([
      { name: "pkg/", typeflag: "5" },
      { name: "pkg/__init__.py", data: enc.encode("x = 1\n") },
      { name: "pkg/tests/test_a.py", data: enc.encode("assert True\n") },
    ]);

    const entries = unpackTar(tar);
    const byName = new Map(entries.map((e) => [e.name, e.data]));

    assert.ok(byName.has("pkg/"));
    assert.deepEqual(byName.get("pkg/__init__.py"), enc.encode("x = 1\n"));
    assert.deepEqual(
      byName.get("pkg/tests/test_a.py"),
      enc.encode("assert True\n"),
    );
  });

  it("joins the ustar prefix field with the name", () => {
    const tar = makeTar([
      { name: "deep/file.py", data: enc.encode("y = 2\n"), prefix: "very/long" },
    ]);
    const entries = unpackTar(tar);
    assert.equal(entries.length, 1);
    assert.equal(entries[0].name, "very/long/deep/file.py");
  });

  it("honors a PAX path header for long names", () => {
    const longPath = "a/".repeat(80) + "leaf.py";
    const record = enc.encode(paxRecord("path", longPath));
    const tar = makeTar([
      { name: "short.py", data: record, typeflag: "x" },
      { name: "short.py", data: enc.encode("z = 3\n") },
    ]);
    const entries = unpackTar(tar);
    assert.equal(entries.length, 1);
    assert.equal(entries[0].name, longPath);
    assert.deepEqual(entries[0].data, enc.encode("z = 3\n"));
  });
});

describe("unpackArchive dispatch", () => {
  it("routes .tar to the tar reader", () => {
    const tar = makeTar([{ name: "a.py", data: enc.encode("a\n") }]);
    const entries = unpackArchive(tar, "pkg-tests.tar");
    assert.equal(entries[0].name, "a.py");
  });

  it("routes .whl/.zip to the zip reader", () => {
    const zip = zipSync({ "a.py": strToU8("a\n") });
    const entries = unpackArchive(zip, "pkg-1.0-none-any.whl");
    assert.equal(entries[0].name, "a.py");
  });

  it("rejects compressed tar before bootstrap", () => {
    assert.throws(
      () => unpackArchive(new Uint8Array(0), "pkg.tar.gz"),
      /not supported before bootstrap/,
    );
  });
});

