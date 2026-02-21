import { describe, it } from "node:test";
import { Installer } from "../../installer.ts";
import { genMockAPI, genMockModule } from "./test-helper.ts";

describe("Installer", () => {
  it("should initialize with API and Module", () => {
    const mockApi = genMockAPI();
    const mockMod = genMockModule();
    const _ = new Installer(mockApi, mockMod);
  });
});
