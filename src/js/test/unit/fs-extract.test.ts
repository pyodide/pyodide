import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { extractArchiveToFS } from "../../package-loading/fs-extract.ts";
import { computePythonPaths } from "../../package-loading/python-paths.ts";
import type { FSType } from "../../types.ts";
import type { ArchiveEntry } from "../../package-loading/archive.ts";

const { extensionTags } = computePythonPaths([3, 14, 2]);
const enc = new TextEncoder();

function makeMockFS() {
  const dirs: string[] = [];
  const files = new Map<string, Uint8Array>();
  const fs = {
    mkdirTree(path: string) {
      dirs.push(path);
    },
    writeFile(path: string, data: Uint8Array) {
      files.set(path, data);
    },
  } as unknown as FSType;
  return { fs, dirs, files };
}

const SITE = "/lib/python3.14/site-packages";

describe("extractArchiveToFS", () => {
  it("writes files, creates parent dirs, and reports dynlibs and metadata dirs", () => {
    const soData = new Uint8Array([0, 97, 115, 109]);
    const entries: ArchiveEntry[] = [
      { name: "pkg/__init__.py", data: enc.encode("x = 1\n") },
      { name: "pkg/_core.cpython-314-wasm32-emscripten.so", data: soData },
      { name: "pkg/_linux.cpython-39-x86_64-linux-gnu.so", data: soData },
      { name: "pkg-1.0.dist-info/METADATA", data: enc.encode("Name: pkg\n") },
      { name: "pkg-1.0.data/data/share/x.txt", data: enc.encode("hi") },
    ];

    const { fs, dirs, files } = makeMockFS();
    const result = extractArchiveToFS(fs, entries, SITE, extensionTags);

    assert.deepEqual(
      files.get(`${SITE}/pkg/__init__.py`),
      enc.encode("x = 1\n"),
    );
    assert.deepEqual(
      files.get(`${SITE}/pkg/_core.cpython-314-wasm32-emscripten.so`),
      soData,
    );
    assert.ok(dirs.includes(`${SITE}/pkg`));

    assert.deepEqual(result.dynlibs, [
      `${SITE}/pkg/_core.cpython-314-wasm32-emscripten.so`,
    ]);
    assert.equal(result.distInfoDir, "pkg-1.0.dist-info");
    assert.equal(result.dataDir, "pkg-1.0.data");
  });

  it("creates directories for explicit directory entries without writing files", () => {
    const entries: ArchiveEntry[] = [
      { name: "pkg/empty/", data: new Uint8Array() },
    ];
    const { fs, dirs, files } = makeMockFS();
    extractArchiveToFS(fs, entries, SITE, extensionTags);
    assert.ok(dirs.includes(`${SITE}/pkg/empty`));
    assert.equal(files.size, 0);
  });

  it("rejects entries that escape the install directory (zip-slip)", () => {
    const entries: ArchiveEntry[] = [
      { name: "../../etc/evil", data: enc.encode("x") },
    ];
    const { fs } = makeMockFS();
    assert.throws(
      () => extractArchiveToFS(fs, entries, SITE, extensionTags),
      /escapes/,
    );
  });

  it("reports no metadata dirs or dynlibs for a plain archive", () => {
    const entries: ArchiveEntry[] = [
      { name: "a.py", data: enc.encode("a") },
      { name: "b/c.txt", data: enc.encode("c") },
    ];
    const { fs } = makeMockFS();
    const result = extractArchiveToFS(fs, entries, SITE, extensionTags);
    assert.deepEqual(result.dynlibs, []);
    assert.equal(result.distInfoDir, undefined);
    assert.equal(result.dataDir, undefined);
  });
});
