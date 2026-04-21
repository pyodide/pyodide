import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { Installer } from "../../installer.ts";
import { genMockAPI, genMockModule } from "./test-helper.ts";

describe("Installer", () => {
  it("should initialize with API and Module", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();
    const _ = new Installer(mockApi, mockMod);
  });

  it("should call package_loader.unpack_buffer.callKwargs", async (t) => {
    // @ts-ignore
    globalThis.DEBUG = false;

    const mockApi = genMockAPI();
    const mockMod = genMockModule();
    const installer = new Installer(mockApi, mockMod);

    const unpackBufferSpy = t.mock.method(
      mockApi.package_loader.unpack_buffer,
      "callKwargs",
      () => [],
    );

    const metadata = new Map<string, string>();
    metadata.set("key", "value");
    await installer.install(
      new Uint8Array(),
      "filename",
      "installDir",
      metadata,
    );

    assert.equal(unpackBufferSpy.mock.callCount(), 1);
    assert.deepEqual(unpackBufferSpy.mock.calls[0].arguments[0], {
      buffer: new Uint8Array(),
      filename: "filename",
      extract_dir: "installDir",
      metadata,
      calculate_dynlibs: true,
    });
  });
});
