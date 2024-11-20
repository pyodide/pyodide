import * as chai from "chai";
import sinon from "sinon";
import { genMockAPI, genMockModule } from "./test-helper.ts";
import { Installer } from "../../installer.ts";

describe("Installer", () => {
  it("should initialize with API and Module", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();
    const _ = new Installer(mockApi, mockMod);
  });

  it("should call package_loader.unpack_buffer.callKwargs", async () => {

    // @ts-ignore
    globalThis.DEBUG = false

    const mockApi = genMockAPI();
    const mockMod = genMockModule();
    const installer = new Installer(mockApi, mockMod);

    const unpackBufferSpy = sinon.stub(mockApi.package_loader.unpack_buffer, "callKwargs").returns([]);

    await installer.install(new Uint8Array(), "filename", "installDir", "installer", "source");

    chai.assert.isTrue(unpackBufferSpy.calledOnce);
    chai.assert.isTrue(unpackBufferSpy.calledWith({
      buffer: new Uint8Array(),
      filename: "filename",
      extract_dir: "installDir",
      installer: "installer",
      source: "source",
      calculate_dynlibs: true,
    }));

    unpackBufferSpy.restore();
  });
});