import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { zipSync, strToU8 } from "fflate";
import { Installer } from "../../installer.ts";
import { genMockAPI, genMockModule } from "./test-helper.ts";
import type { PackageManagerModule } from "../../types.ts";

// @ts-ignore
globalThis.DEBUG = false;

const dec = new TextDecoder();

function moduleWithRecordingFS() {
  const files = new Map<string, Uint8Array>();
  const dirs: string[] = [];
  const mod = genMockModule();
  (mod as PackageManagerModule).FS = {
    mkdirTree: (path: string) => {
      dirs.push(path);
    },
    writeFile: (path: string, data: Uint8Array) => {
      files.set(path, data);
    },
  } as unknown as PackageManagerModule["FS"];
  return { mod, files, dirs };
}

function makeWheel() {
  return zipSync({
    "dummy_pkg/__init__.py": strToU8("__version__ = '0.1.0'\n"),
    "dummy_pkg/_core.cpython-314-wasm32-emscripten.so": new Uint8Array([
      // \0asm
      0, 97, 115, 109,
    ]),
    "dummy_pkg-0.1.0.dist-info/METADATA": strToU8(
      "Metadata-Version: 2.1\nName: dummy_pkg\n",
    ),
    "dummy_pkg-0.1.0.data/data/share/dummy/data.txt": strToU8("hello"),
  });
}

describe("Installer", () => {
  it("initializes with API and Module", () => {
    const _ = new Installer(genMockAPI(), genMockModule());
  });

  it("extracts wheel contents into the install directory", async () => {
    const { mod, files } = moduleWithRecordingFS();
    const installer = new Installer(genMockAPI(), mod);

    await installer.install(
      makeWheel(),
      "dummy_pkg-0.1.0-py3-none-any.whl",
      "/site",
    );

    assert.equal(
      dec.decode(files.get("/site/dummy_pkg/__init__.py")),
      "__version__ = '0.1.0'\n",
    );
    assert.ok(
      files.has("/site/dummy_pkg/_core.cpython-314-wasm32-emscripten.so"),
    );
    assert.ok(files.has("/site/dummy_pkg-0.1.0.dist-info/METADATA"));
  });

  it("writes metadata files into the dist-info directory", async () => {
    const { mod, files } = moduleWithRecordingFS();
    const installer = new Installer(genMockAPI(), mod);

    await installer.install(
      makeWheel(),
      "dummy_pkg-0.1.0-py3-none-any.whl",
      "/site",
      new Map([
        ["INSTALLER", "pytest"],
        ["PYODIDE_SOURCE", "pyodide"],
      ]),
    );

    assert.equal(
      dec.decode(files.get("/site/dummy_pkg-0.1.0.dist-info/INSTALLER")),
      "pytest",
    );
    assert.equal(
      dec.decode(files.get("/site/dummy_pkg-0.1.0.dist-info/PYODIDE_SOURCE")),
      "pyodide",
    );
  });

  it("installs data files relative to sys.prefix", async () => {
    const { mod, files } = moduleWithRecordingFS();
    const installer = new Installer(genMockAPI(), mod);

    await installer.install(
      makeWheel(),
      "dummy_pkg-0.1.0-py3-none-any.whl",
      "/site",
    );

    assert.equal(dec.decode(files.get("/share/dummy/data.txt")), "hello");
  });

  it("loads the shared libraries found in the wheel", async (t) => {
    const { mod } = moduleWithRecordingFS();
    const dlopenSpy = t.mock.method(mod, "_emscripten_dlopen_promise", () => 0);
    const installer = new Installer(genMockAPI(), mod);

    await installer.install(
      makeWheel(),
      "dummy_pkg-0.1.0-py3-none-any.whl",
      "/site",
    );

    assert.equal(dlopenSpy.mock.callCount(), 1);
  });
});
