import assert from "assert";
import { initializePackageCache } from "../load-pyodide.js";
import fs from "fs";

describe("Package cache", () => {
  it("initializePackageCache", async () => {
    let cacheDir = await initializePackageCache();
    assert.equal(fs.existsSync(cacheDir), true);
  });
});
